# Day 28 — Capstone Architecture, Repo Strategy, Cost Strategy
## Reference Document

> Chứa architecture diagram đầy đủ, repo structure template, ADR drafts, cost matrix, security checklist, cleanup runbook, environment strategy, và anti-patterns.

---

## A. Architecture Diagram — Mode A (Local)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     MODE A: LOCAL / KIND + FREE STACK                        │
│                     Giả lập production stack trên developer machine          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │                      DEVELOPER LAPTOP / WORKSTATION                  │    │
│  │                                                                        │    │
│  │  ┌──────────────────────────────────────────────────────────────┐   │    │
│  │  │              Docker Desktop / Docker Engine                   │   │    │
│  │  │                                                                  │   │    │
│  │  │  ┌────────────────────────────────────────────────────┐   │   │    │
│  │  │  │  kind cluster: capstone (kubernetes.io/kind)       │   │   │    │
│  │  │  │                                                       │   │   │    │
│  │  │  │  ┌─────────── NAMESPACE: argocd ─────────────────┐   │   │    │
│  │  │  │  │  argocd-server        (ClusterIP, port 443)    │   │   │    │
│  │  │  │  │  argocd-repo-server   (Deployment)            │   │   │    │
│  │  │  │  │  argocd-application-controller (Deployment)   │   │   │    │
│  │  │  │  └────────────────────────────────────────────────┘   │   │    │
│  │  │  │                                                        │   │    │
│  │  │  │  ┌─────────── NAMESPACE: ingress-nginx ────────────┐   │   │    │
│  │  │  │  │  ingress-nginx-controller        (DaemonSet)      │   │   │    │
│  │  │  │  │  Service: NodePort 80/443                         │   │   │    │
│  │  │  │  └────────────────────────────────────────────────┘   │   │    │
│  │  │  │                                                        │   │    │
│  │  │  │  ┌─────────── NAMESPACE: cert-manager ──────────────┐   │   │    │
│  │  │  │  │  cert-manager              (Deployment)            │   │   │    │
│  │  │  │  │  cert-manager-webhook     (Deployment)           │   │   │    │
│  │  │  │  │  ClusterIssuer: self-signed (for *.local.dev)    │   │   │    │
│  │  │  │  └────────────────────────────────────────────────┘   │   │    │
│  │  │  │                                                        │   │    │
│  │  │  │  ┌─────────── NAMESPACE: external-secrets ──────────┐   │   │    │
│  │  │  │  │  external-secrets-controller   (Deployment)      │   │   │    │
│  │  │  │  │  SecretStore: ClusterSecretStore (fake/vault)    │   │   │    │
│  │  │  │  └────────────────────────────────────────────────┘   │   │    │
│  │  │  │                                                        │   │    │
│  │  │  │  ┌─────────── NAMESPACE: monitoring ───────────────┐   │   │    │
│  │  │  │  │  prometheus              (StatefulSet/Deployment)│   │   │    │
│  │  │  │  │  prometheus-server      (Deployment)             │   │   │    │
│  │  │  │  │  grafana                (Deployment)             │   │   │    │
│  │  │  │  │  kube-state-metrics    (Deployment)             │   │   │    │
│  │  │  │  │  node-exporter         (DaemonSet)             │   │   │    │
│  │  │  │  └────────────────────────────────────────────────┘   │   │    │
│  │  │  │                                                        │   │    │
│  │  │  │  ┌─────────── NAMESPACE: api-service ───────────────┐   │   │    │
│  │  │  │  │  api-service              (Deployment, 2 replicas) │   │   │    │
│  │  │  │  │  api-service             (Service: ClusterIP 8080)│   │   │    │
│  │  │  │  │  api-service             (HPA, max 5 replicas)   │   │   │    │
│  │  │  │  └────────────────────────────────────────────────┘   │   │    │
│  │  │  │                                                        │   │    │
│  │  │  │  ┌─────────── NAMESPACE: worker-service ────────────┐   │   │    │
│  │  │  │  │  worker-service            (Deployment, 1 replica) │   │   │    │
│  │  │  │  └────────────────────────────────────────────────┘   │   │    │
│  │  │  │                                                        │   │    │
│  │  │  │  ┌─────────── NAMESPACE: frontend-service ───────────┐   │   │    │
│  │  │  │  │  frontend-service         (Deployment, 2 replicas)│   │   │    │
│  │  │  │  │  frontend-service        (Service: ClusterIP 3000)│  │   │    │
│  │  │  │  └────────────────────────────────────────────────┘   │   │    │
│  │  │  └──────────────────────────────────────────────────────┘   │    │
│  │  └──────────────────────────────────────────────────────────────┘    │
│  └────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │                Docker Compose (chạy ngoài kind cluster)              │    │
│  │                                                                        │    │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐   │    │
│  │  │ PostgreSQL    │  │    Redis     │  │  LocalStack (opt)    │   │    │
│  │  │  port 5432   │  │   port 6379  │  │  mock: S3, SQS, IAM  │   │    │
│  │  │  user: cap   │  │  user: cap   │  │  port 4566           │   │    │
│  │  │  pass: ***   │  │  pass: ***   │  │                      │   │    │
│  │  │  vol: pgdata │  │  vol: redis  │  │                      │   │    │
│  │  └──────────────┘  └──────────────┘  └──────────────────────┘   │    │
│  └────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │             GitHub Container Registry (ghcr.io)                     │    │
│  │                                                                        │    │
│  │  ghcr.io/<user>/api-service:v1.0.0                                   │    │
│  │  ghcr.io/<user>/worker-service:v1.0.0                               │    │
│  │  ghcr.io/<user>/frontend-service:v1.0.0                             │    │
│  └────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │             GitHub Actions (external CI, trigger on push)            │    │
│  │                                                                        │    │
│  │  workflow: ci.yml → lint → test → build → scan → push to ghcr.io  │    │
│  │  workflow: image-bump.yml → detect new tag → PR to apps-repo       │    │
│  └────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  COST: $0/month (excludes Docker Desktop license if applicable)              │
│  SETUP TIME: ~15-20 phút                                                   │
│  TEARDOWN: kind delete cluster → ~2 phút                                    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## B. Architecture Diagram — Mode B (AWS)

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                      MODE B: AWS / EKS + PRODUCTION STACK                        │
│                      Production-grade infrastructure trên AWS                     │
├──────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ┌────────────────────────────────────────────────────────────────────────────┐  │
│  │                          AWS REGION: eu-west-1 / us-east-1                   │  │
│  │                                                                              │  │
│  │  ┌──────────────────────────────────────────────────────────────────────┐  │  │
│  │  │                        VPC: capstone-vpc (10.0.0.0/16)                │  │  │
│  │  │                                                                        │  │  │
│  │  │  ┌── PUBLIC SUBNETS ───────────────────────────────────────────────┐  │  │  │
│  │  │  │  subnet-0a (10.0.0.0/24, eu-west-1a)                           │  │  │  │
│  │  │  │  subnet-0b (10.0.1.0/24, eu-west-1b)                           │  │  │  │
│  │  │  │                                                                        │  │  │  │
│  │  │  │  ┌─────────────────────────────────────────────────────────┐  │  │  │  │
│  │  │  │  │  NAT Gateway (10.0.0.10) — $32.50/mo                    │  │  │  │  │
│  │  │  │  │  EIP attached                                            │  │  │  │  │
│  │  │  │  └─────────────────────────────────────────────────────────┘  │  │  │  │
│  │  │  │                                                                        │  │  │  │
│  │  │  │  ┌─────────────────────────────────────────────────────────┐  │  │  │  │
│  │  │  │  │  Application Load Balancer (ALB) — $16.50/mo           │  │  │  │  │
│  │  │  │  │  Target Groups: api, worker, frontend                  │  │  │  │  │
│  │  │  │  │  Listeners: HTTPS 443 (ACM cert) → HTTP 80             │  │  │  │  │
│  │  │  │  │  Security Group: allow 443 from 0.0.0.0/0              │  │  │  │  │
│  │  │  │  └─────────────────────────────────────────────────────────┘  │  │  │  │
│  │  │  │                                                                        │  │  │  │
│  │  │  │  ┌─────────────────────────────────────────────────────────┐  │  │  │  │
│  │  │  │  │  VPC Endpoints (free):                                  │  │  │  │  │
│  │  │  │  │  com.amazonaws.eu-west-1.s3 (gateway)                   │  │  │  │  │
│  │  │  │  │  com.amazonaws.eu-west-1.ecr.dkr (interface)           │  │  │  │  │
│  │  │  │  │  com.amazonaws.eu-west-1.secretsmanager (interface)   │  │  │  │  │
│  │  │  │  │  com.amazonaws.eu-west-1.ecr.api (interface)           │  │  │  │  │
│  │  │  │  └─────────────────────────────────────────────────────────┘  │  │  │  │
│  │  │  └──────────────────────────────────────────────────────────────┘  │  │  │
│  │  │                                                                        │  │  │
│  │  │  ┌── PRIVATE SUBNETS (EKS Nodes) ─────────────────────────────┐  │  │  │
│  │  │  │  subnet-0c (10.0.16.0/24, eu-west-1a)                     │  │  │  │
│  │  │  │  subnet-0d (10.0.17.0/24, eu-west-1b)                     │  │  │  │
│  │  │  │                                                                        │  │  │  │
│  │  │  │  ┌─────────────────────────────────────────────────────────┐  │  │  │  │
│  │  │  │  │  EKS Managed Node Group: capstone-nodes                │  │  │  │  │
│  │  │  │  │  Instance type: t3.medium × 2 (On-Demand)             │  │  │  │  │
│  │  │  │  │  Instance type: t3.medium × 1 (Spot, 30% of nodes)   │  │  │  │  │
│  │  │  │  │  AMI: AL2023, Kubernetes 1.30                          │  │  │  │  │
│  │  │  │  │  Desired capacity: 2, Max: 4, Min: 1                  │  │  │  │  │
│  │  │  │  └─────────────────────────────────────────────────────────┘  │  │  │  │
│  │  │  │                                                                        │  │  │  │
│  │  │  │  [EKS PODS running in private subnets]                        │  │  │  │
│  │  │  │                                                                        │  │  │  │
│  │  │  │  ┌── Pod: aws-load-balancer-controller ───────────────────┐  │  │  │  │
│  │  │  │  │  IRSA: aws-lb-controller-role                         │  │  │  │  │
│  │  │  │  └───────────────────────────────────────────────────────┘  │  │  │  │
│  │  │  │  ┌── Pod: cert-manager ──────────────────────────────────┐  │  │  │  │
│  │  │  │  │  IRSA: cert-manager-role                             │  │  │  │  │
│  │  │  │  └───────────────────────────────────────────────────────┘  │  │  │  │
│  │  │  │  ┌── Pod: external-secrets ─────────────────────────────┐  │  │  │  │
│  │  │  │  │  IRSA: external-secrets-role                        │  │  │  │  │
│  │  │  │  │  → reads from: AWS Secrets Manager                   │  │  │  │  │
│  │  │  │  └───────────────────────────────────────────────────────┘  │  │  │  │
│  │  │  │  ┌── Pod: argocd-server ────────────────────────────────┐  │  │  │  │
│  │  │  │  │  Service: ClusterIP (accessed via Ingress/ALB)      │  │  │  │  │
│  │  │  │  └───────────────────────────────────────────────────────┘  │  │  │  │
│  │  │  │  ┌── Pod: kube-prometheus-stack ───────────────────────┐  │  │  │  │
│  │  │  │  │  Prometheus → scrapes all pod metrics (port 9100)   │  │  │  │  │
│  │  │  │  │  Grafana → dashboards                                │  │  │  │  │
│  │  │  │  └───────────────────────────────────────────────────────┘  │  │  │  │
│  │  │  │  ┌── Pod: api-service ──────────────────────────────────┐  │  │  │  │
│  │  │  │  │  Replicas: 2-5 (HPA)                                 │  │  │  │  │
│  │  │  │  │  IRSA: api-service-role → Secrets Manager           │  │  │  │  │
│  │  │  │  │  → reads DB_HOST, DB_PASS, REDIS_URL from ASM       │  │  │  │  │
│  │  │  │  └───────────────────────────────────────────────────────┘  │  │  │  │
│  │  │  │  ┌── Pod: worker-service ──────────────────────────────┐  │  │  │  │
│  │  │  │  │  Replicas: 1-2 (HPA)                                 │  │  │  │  │
│  │  │  │  │  IRSA: worker-service-role → Secrets Manager       │  │  │  │  │
│  │  │  │  └───────────────────────────────────────────────────────┘  │  │  │  │
│  │  │  │  ┌── Pod: frontend-service ────────────────────────────┐  │  │  │  │
│  │  │  │  │  Replicas: 2-3 (HPA)                                 │  │  │  │  │
│  │  │  │  │  Service: ClusterIP → ALB via ingress-nginx         │  │  │  │  │
│  │  │  │  └───────────────────────────────────────────────────────┘  │  │  │  │
│  │  │  └──────────────────────────────────────────────────────────────┘  │  │  │
│  │  │                                                                        │  │  │
│  │  │  ┌── PRIVATE SUBNETS (DATA) ─────────────────────────────────┐  │  │  │
│  │  │  │  subnet-0e (10.0.32.0/24, eu-west-1a)                   │  │  │  │
│  │  │  │  subnet-0f (10.0.33.0/24, eu-west-1b)                   │  │  │  │
│  │  │  │                                                                        │  │  │  │
│  │  │  │  ┌─────────────────────────────────────────────────────────┐  │  │  │  │
│  │  │  │  │  RDS PostgreSQL (Multi-AZ) — $70/mo                   │  │  │  │  │
│  │  │  │  │  Instance: db.t3.medium                              │  │  │  │  │
│  │  │  │  │  Storage: 100GB gp3                                   │  │  │  │  │
│  │  │  │  │  Multi-AZ: yes (eu-west-1a ↔ eu-west-1b)            │  │  │  │  │
│  │  │  │  │  PubliclyAccessible: NO                               │  │  │  │  │
│  │  │  │  │  Security Group: port 5432 from EKS nodes only       │  │  │  │  │
│  │  │  │  │  Backup: daily, retention 7 days                     │  │  │  │  │
│  │  │  │  └─────────────────────────────────────────────────────────┘  │  │  │  │
│  │  │  │                                                                        │  │  │  │
│  │  │  │  ┌─────────────────────────────────────────────────────────┐  │  │  │  │
│  │  │  │  │  ElastiCache Redis — $25/mo                            │  │  │  │  │
│  │  │  │  │  Instance: cache.t3.medium                            │  │  │  │  │
│  │  │  │  │  Engine: redis 7.x                                    │  │  │  │  │
│  │  │  │  │  Replication: disabled (single-node dev)              │  │  │  │  │
│  │  │  │  │  Auth: yes (token)                                    │  │  │  │  │
│  │  │  │  └─────────────────────────────────────────────────────────┘  │  │  │  │
│  │  │  └──────────────────────────────────────────────────────────────┘  │  │  │
│  │  └──────────────────────────────────────────────────────────────────────┘  │  │
│  └────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                  │
│  ┌───────────────┐  ┌──────────────┐  ┌──────────────┐  ┌─────────────────┐   │
│  │     ECR       │  │  Route 53    │  │     ACM      │  │ Secrets Manager │   │
│  │  ghcr.io equiv│  │  DNS zones   │  │  TLS certs   │  │  ESO pull from  │   │
│  │  cap-*/api    │  │  cap.dev     │  │  *.cap.dev  │  │  prod/api-svc   │   │
│  │  cap-*/worker │  │  cap.staging │  │  (wildcard) │  │  prod/worker    │   │
│  │  cap-*/frontend│  │  cap.prod    │  │  Free       │  │  prod/db-creds  │   │
│  └───────────────┘  └──────────────┘  └──────────────┘  └─────────────────┘   │
│                                                                                  │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │  GitHub Actions (external, NOT in AWS)                                    │   │
│  │                                                                          │   │
│  │  OIDC trust: GitHub → AWS IAM Role (no long-lived credentials)         │   │
│  │  workflow ci.yml: lint → test → build → trivy scan → push ECR         │   │
│  │  workflow image-bump.yml: detect new tag → PR to capstone-apps          │   │
│  └──────────────────────────────────────────────────────────────────────────┘   │
│                                                                                  │
│  COST: ~$277/month (full) | ~$180/month (cost-optimized)                        │
│  SETUP TIME: ~45-60 phút                                                        │
│  TEARDOWN: make aws-destroy → ~10-15 phút                                       │
│                                                                                  │
└──────────────────────────────────────────────────────────────────────────────────┘
```

---

## C. Repository Structure Template (đầy đủ)

```
capstone-infra/                          # ★ SRE/DevOps owns
│
├── .github/
│   └── workflows/
│       ├── terraform-fmt.yml
│       ├── terraform-validate.yml
│       ├── terraform-plan.yml           # PR: plan only
│       └── terraform-apply.yml          # merge main: apply
│
├── modules/                             # Terraform modules reuse
│   ├── network/                         # VPC, subnets, route tables, NAT GW
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   ├── outputs.tf
│   │   └── versions.tf
│   ├── eks/                             # EKS cluster, node groups, IRSA
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   ├── outputs.tf
│   │   └── versions.tf
│   ├── rds/                             # RDS PostgreSQL
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   ├── outputs.tf
│   │   └── versions.tf
│   ├── elasticache/                     # ElastiCache Redis
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   ├── outputs.tf
│   │   └── versions.tf
│   └── irsa/                           # IAM role for ServiceAccount
│       ├── main.tf
│       ├── variables.tf
│       └── outputs.tf
│
├── live/                                # Environment-specific
│   ├── dev/
│   │   ├── main.tf                     # module "vpc" { source = "../../../modules/network" }
│   │   ├── variables.tf
│   │   ├── terraform.tfvars            # environment = "dev"
│   │   └── outputs.tf
│   ├── staging/
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   ├── terraform.tfvars
│   │   └── outputs.tf
│   └── prod/
│       ├── main.tf
│       ├── variables.tf
│       ├── terraform.tfvars
│       └── outputs.tf
│
├── docs/
│   ├── adr/                            # Architecture Decision Records
│   │   ├── 0001-mode-a-vs-b.md
│   │   ├── 0002-repo-split.md
│   │   ├── 0003-secrets-strategy.md
│   │   ├── 0004-promotion-flow.md
│   │   └── 0005-disaster-recovery.md
│   ├── architecture.md                  # ASCII diagram + module breakdown
│   ├── cost-estimate.md                # AWS cost table + cleanup
│   └── security-baseline.md            # Security checklist
│
├── Makefile
├── .gitignore
├── .terraform-version
├── versions.tf                         # terraform { required_providers }
├── backend.tf                          # S3 + DynamoDB backend
├── CODEOWNERS
└── README.md


capstone-platform/                      # ★ Platform team owns
│
├── .github/
│   └── workflows/
│       ├── conftest.yml                # OPA policy check
│       └── kustomize-build.yml         # validate overlays
│
├── argocd/
│   ├── bootstrap/
│   │   └── root-app.yaml               # Root Application (App of Apps)
│   ├── projects/
│   │   ├── platform-project.yaml
│   │   └── team-project.yaml
│   └── applications/
│       ├── ingress-nginx.yaml          # NGINX Ingress / AWS LB Controller
│       ├── cert-manager.yaml
│       ├── external-secrets.yaml
│       ├── prometheus-stack.yaml
│       └── loki.yaml
│
├── platform-services/                  # Helm values (upstream charts)
│   ├── ingress-nginx/
│   │   └── values.yaml
│   ├── cert-manager/
│   │   └── values.yaml
│   ├── external-secrets/
│   │   ├── values.yaml
│   │   └── cluster-secret-store.yaml
│   └── prometheus-stack/
│       └── values.yaml
│
├── policies/                           # OPA / Kyverno
│   ├── disallow-latest-tag.yaml
│   └── require-resources.yaml
│
├── .gitignore
├── CODEOWNERS
└── README.md


capstone-apps/                          # ★ App teams own per service
│
├── .github/
│   └── workflows/
│       ├── kustomize-build.yml         # validate overlays
│       ├── image-bump.yml              # auto PR when new image available
│       └── promote.yml                  # manual promotion PR
│
├── services/
│   ├── api-service/
│   │   ├── base/
│   │   │   ├── deployment.yaml
│   │   │   ├── service.yaml
│   │   │   ├── hpa.yaml
│   │   │   ├── configmap.yaml
│   │   │   ├── serviceaccount.yaml     # IRSA annotation
│   │   │   └── kustomization.yaml
│   │   └── overlays/
│   │       ├── dev/
│   │       │   ├── kustomization.yaml
│   │       │   └── resources-patch.yaml
│   │       ├── staging/
│   │       │   ├── kustomization.yaml
│   │       │   └── resources-patch.yaml
│   │       └── prod/
│   │           ├── kustomization.yaml
│   │           ├── resources-patch.yaml
│   │           └── strategy-patch.yaml   # PodDisruptionBudget, topology spread
│   │
│   ├── worker-service/
│   │   ├── base/
│   │   │   ├── deployment.yaml
│   │   │   ├── configmap.yaml
│   │   │   ├── serviceaccount.yaml
│   │   │   └── kustomization.yaml
│   │   └── overlays/{dev,staging,prod}/
│   │
│   └── frontend-service/
│       ├── base/
│       │   ├── deployment.yaml
│       │   ├── service.yaml
│       │   ├── ingress.yaml             # cert-manager annotation
│       │   ├── configmap.yaml
│       │   ├── serviceaccount.yaml
│       │   └── kustomization.yaml
│       └── overlays/{dev,staging,prod}/
│
├── argocd/
│   ├── projects/
│   │   └── api-team-project.yaml
│   └── applications/
│       ├── api-service-dev.yaml
│       ├── api-service-staging.yaml
│       ├── api-service-prod.yaml
│       ├── worker-service-dev.yaml
│       ├── worker-service-staging.yaml
│       ├── worker-service-prod.yaml
│       ├── frontend-service-dev.yaml
│       ├── frontend-service-staging.yaml
│       └── frontend-service-prod.yaml
│
├── .gitignore
├── CODEOWNERS
└── README.md
```

---

## D. ADR Template + 5 ADR Drafts

### ADR Template

```markdown
# ADR-XXXX: <Title>

## Status
Proposed | Accepted | Deprecated | Superseded

## Date
YYYY-MM-DD

## Context
[Vấn đề cần giải quyết. Mô tả ràng buộc, stakeholder, options đã xem xét.]

## Decision
[Quyết định cụ thể đã chọn. Diễn đạt rõ ràng, không mơ hồ.]

## Options Considered

| Option | Pros | Cons |
|--------|------|------|
| A | ... | ... |
| B | ... | ... |

## Consequences

### Positive
- ...

### Negative
- ...

### Neutral
- ...
```

---

### ADR-0001: Mode A (Local) là Default cho Capstone

```markdown
# ADR-0001: Mode A (Local) là Default cho Capstone

## Status
Accepted — 2026-05-15

## Context
Capstone (Day 28-35) phục vụ 2 nhóm learner: (1) không có AWS account/credit card, (2) muốn mô phỏng production AWS. Cần 1 architectural decision về default mode.

## Decision
Mode A (kind + free stack) là default. Mode B (AWS/EKS) available như optional track.

## Consequences

### Positive
- Mọi học viên đều hoàn thành được Capstone
- Fast feedback loop, tập trung GitOps pattern
- Không có risk của accidental AWS bill

### Negative
- Không trải nghiệm IRSA, RDS Multi-AZ, ALB Controller thực sự
- Mode B documentation tăng effort cho instructor

### Neutral
- AWS-specific components vẫn được giới thiệu qua code review trong Day 32-34
```

---

### ADR-0002: 3-repo Polyrepo cho Capstone

```markdown
# ADR-0002: 3-repo Polyrepo cho Capstone

## Status
Accepted — 2026-05-15

## Context
Capstone có 3 concern tách biệt: infrastructure (Terraform), platform (cluster addons), và application (microservices). Cần quyết định tổ chức repo.

## Decision
3-repo polyrepo:
- `capstone-infra/`: Terraform code (SRE owns)
- `capstone-platform/`: cluster-level Helm values + ArgoCD Applications (Platform team owns)
- `capstone-apps/`: microservice manifests + Kustomize overlays (App teams own)

Solo learner có thể dùng 3 folder trong 1 repo thay vì 3 remote repo.

## Consequences

### Positive
- Ownership boundary rõ: SRE/app teams không sửa Terraform của nhau
- CI trigger chính xác: infra change không trigger app build
- Simulate production-grade team structure
- Blast radius nhỏ: 1 repo breach không ảnh hưởng cả stack

### Negative
- Cross-cutting change (VD: thêm label vào tất cả namespaces) cần 3 PR
- Onboarding: cần clone 3 repo thay vì 1
- Tooling consistency cần được sync giữa 3 repo
```

---

### ADR-0003: ESO + AWS Secrets Manager cho Secret Management

```markdown
# ADR-0003: External Secrets Operator + AWS Secrets Manager

## Status
Proposed — 2026-05-15

## Context
Microservices cần database credentials, Redis password, API keys. Cách lưu trữ và inject secret vào pod cần được chuẩn hóa.

## Decision
Dùng External Secrets Operator (ESO) với AWS Secrets Manager (Mode B) hoặc ESO local provider (Mode A).

Mode B:
- ESO Sync: AWS Secrets Manager → Kubernetes Secret
- IRSA gắn với ESO ServiceAccount → không cần long-lived AWS credentials
- Pod chỉ đọc Kubernetes Secret (không biết về ASM)

Mode A:
- ESO với ClusterSecretStore + fake provider hoặc HashiCorp Vault dev mode
- Không có real ASM, chỉ demo flow

## Consequences

### Positive
- Secret không nằm trong Git (không commit plain text)
- Rotation: update ASM → ESO sync → pod reload không restart
- Audit: xem ai đọc secret từ CloudTrail
- DR: ASM có replication, ESO config có thể restore

### Negative
- ESO Operator cần bootstrap (Day 32)
- ASM cost: $0.40/secret/month (nhỏ, ~$5 cho 12 secrets)
- Chicken-and-egg: ESO cần IAM role → IAM role tạo bằng Terraform (infra) → ESO chạy trong cluster (platform) → conflict ownership
```

---

### ADR-0004: Promotion qua Pull Request, không dùng argocd app sync

```markdown
# ADR-0004: Promotion qua Pull Request, không dùng argocd app sync

## Status
Proposed — 2026-05-15

## Context
Cần chuẩn hóa cách promote application version từ dev → staging → prod. Có 2 approach: (A) PR thay đổi Git tag, (B) trực tiếp chạy `argocd app sync`.

## Decision
Promotion luôn qua Pull Request thay đổi `newTag` trong `kustomization.yaml`. Không dùng `argocd app sync` làm promotion mechanism.

Promotion flow:
1. CI build image → push: `v1.2.3`
2. Renovate/ArgoCD Image Updater detect → auto PR vào `overlays/dev/`
3. CI validate → auto-merge → ArgoCD dev sync
4. Manual PR: `overlays/dev/` → `overlays/staging/` (1 reviewer)
5. Manual PR: `overlays/staging/` → `overlays/prod/` (2 approvals + SRE lead)

## Consequences

### Positive
- Audit trail: mọi promotion có PR, reviewer, timestamp
- Rollback = `git revert` → Git = cluster (single source of truth)
- Security: prod promotion cần 2-4 người approve
- Compliance: PR merge log là audit log

### Negative
- Chậm hơn `argocd app sync` trực tiếp (thêm 5-10 phút cho PR review)
- Cần discipline: developer không bypass PR
```

---

### ADR-0005: Disaster Recovery Strategy

```markdown
# ADR-0005: Disaster Recovery Strategy

## Status
Proposed — 2026-05-15

## Context
Cần có plan cho các disaster scenarios: mất cluster, mất ArgoCD, sai secret, deployment lỗi, Terraform state corruption.

## Decision

### RPO (Recovery Point Objective): 24 giờ
- Database: RDS automated backup daily, retention 7 days
- ArgoCD repo: GitHub là source of truth — không mất
- Terraform state: S3 versioning + DynamoDB lock

### RTO (Recovery Time Objective): 2 giờ cho tier-1, 24 giờ cho tier-2

### DR Scenarios

| Scenario | Recovery | RTO | RPO |
|----------|----------|-----|-----|
| Cluster lost | Recreate EKS + ArgoCD bootstrap + re-sync GitOps | 2h | 0 (GitOps) |
| ArgoCD deleted | Restore from Git + kubectl apply ArgoCD CRD | 30m | 0 |
| Bad deployment | git revert → ArgoCD auto-sync | 5m | 0 |
| Database corruption | RDS point-in-time restore | 1h | 15min |
| Terraform state lost | S3 version restore | 30m | 0 |
| Secrets leak | Rotate immediately + IRSA detach + notify | 15m | 0 |

## Consequences

### Positive
- GitOps = inherent DR (redeploy = re-sync Git)
- RDS automated backup = low-effort DB recovery
- S3 versioning = Terraform state recovery

### Negative
- Cluster DR cần practice (Day 35 simulate)
- RTO 2h cho tier-1 = business acceptance required
```

---

## E. Cost Matrix — Mode B (AWS, eu-west-1, tháng 5/2026)

| Service | Spec | On-Demand $/tháng | Spot $/tháng | Notes |
|---------|------|------------------|--------------|-------|
| EKS Control Plane | 1 cluster | $73.00 | $73.00 | Flat rate, không giảm được |
| EC2 (Node Group) | t3.medium × 2 | $45.20 | — | $0.0416/hr × 730h × 2 |
| EC2 (Spot Mix) | t3.medium × 1 (30%) | — | $9.20 | 70% savings vs OD |
| RDS PostgreSQL Multi-AZ | db.t3.medium 100GB | $70.00 | $70.00 | $0.115/hr × 2 (Multi-AZ) |
| RDS PostgreSQL Single-AZ | db.t3.small 50GB | $25.00 | $25.00 | Dev/staging only |
| ElastiCache Redis | cache.t3.medium | $25.00 | $25.00 | Single-AZ; Multi-AZ $50 |
| NAT Gateway | 1 AZ | $32.50 | $32.50 | $0.045/hr + $0.045/GB |
| ALB | 1 | $16.50 | $16.50 | $0.0225/LCU + base |
| Secrets Manager | 5 secrets | $1.35 | $1.35 | $0.40/secret |
| Route 53 | 1 hosted zone | $0.50 | $0.50 | |
| ECR storage | ~5 GB | $0.45 | $0.45 | $0.10/GB |
| CloudWatch metrics | ~100 custom | $3.00 | $3.00 | $0.30/metric |
| **Total (full prod)** | | **~$267-277** | **~$237** | |
| **Total (dev only, Spot+SingleAZ)** | | **~$142** | **~$142** | |

### Cost Optimization Strategies

```
Strategy 1: VPC Endpoint thay NAT Gateway
  Before: NAT Gateway ($32.50/mo) + Internet Gateway
  After:  S3 VPC Endpoint ($0) + ECR VPC Endpoint ($0) + Secrets Manager VPC Endpoint ($0)
  Saving: ~$25/mo (worker pod vẫn cần NAT cho external API calls)
  Note:   Nếu tất cả external calls đi qua VPC endpoint → xóa NAT

Strategy 2: Spot Node cho non-prod
  On-Demand t3.medium × 2 → Spot t3.medium × 1 + OD × 1
  Saving: ~$36/mo (70% savings on mixed workload)
  Note:   Cần graceful shutdown handling (eksctl/node termination handler)

Strategy 3: Single-AZ cho dev/staging
  Multi-AZ RDS → Single-AZ RDS cho dev/staging
  Saving: ~$45/mo cho mỗi non-prod env

Strategy 4: t3.small cho dev
  t3.medium → t3.small cho dev cluster
  Saving: ~$22/mo

Strategy 5: Dev dùng kind, không EKS
  Xóa EKS dev cluster → dùng kind trên local
  Saving: ~$73/mo (EKS) + ~$25/mo (RDS Single-AZ) + ~$15/mo (ALB)
  Total: ~$113/mo cho dev environment
```

---

## F. Security Baseline Checklist (20 bullets)

### MUST — bắt buộc

- [ ] **IRSA**: tất cả pod cần AWS access dùng IRSA (IAM Role for ServiceAccount), không access key trong env var
- [ ] **OIDC GitHub Actions**: dùng OIDC trust thay vì `AWS_ACCESS_KEY_ID` + `AWS_SECRET_ACCESS_KEY` trong GitHub secrets
- [ ] **IAM least-privilege**: role chỉ grant permission cần thiết (VD: `secretsmanager:GetSecretValue` + exact secret ARN, không `secretsmanager:*`)
- [ ] **RDS private subnet**: không có PubliclyAccessible, security group chỉ allow port 5432 từ EKS node SG
- [ ] **ElastiCache private**: no public IP, auth token enabled
- [ ] **Secret không trong Git**: dùng ESO + ASM thay vì commit base64 vào repo
- [ ] **Immutable image tag**: dùng `v1.2.3` hoặc digest, KHÔNG `latest`
- [ ] **Container scan**: Trivy/Grype scan image trước khi push ECR
- [ ] **Terraform state**: S3 + DynamoDB lock, không local state
- [ ] **No hardcode**: không account ID, region, password thật trong code/documentation

### SHOULD — nên làm

- [ ] **ArgoCD RBAC**: không dùng built-in `admin` role cho người dùng thường
- [ ] **ArgoCD admin rotation**: đổi admin password định kỳ hoặc dùng SSO
- [ ] **EKS API endpoint**: private endpoint enabled, public endpoint disabled hoặc restricted by SG
- [ ] **Container resources**: requests/limits trên mọi container (tránh noisy-neighbor)
- [ ] **Spot termination handler**: nếu dùng Spot node, enable `aws-node-termination-handler`
- [ ] **Database password auto-gen**: Terraform `random_password` resource, không dùng default
- [ ] **HPA**: có HPA cho mọi Deployment, tránh single point of failure
- [ ] **PDB**: PodDisruptionBudget cho prod deployments (minimum 1 pod during updates)

### NICE-TO-HAVE

- [ ] **OPA/Gatekeeper**: policy disallow privileged container, no hostPID/hostNetwork
- [ ] **Signed commits**: GPG/Sigstore signed commits cho production merges
- [ ] **VPC Flow Logs**: enable cho audit và security analysis
- [ ] **AWS GuardDuty**: enable cho production AWS account

---

## G. Cleanup Runbook — Mode B (AWS)

> Quan trọng: Chạy sau mỗi lab session để tránh bill không mong muốn.

### Normal Cleanup (Terraform destroy)

```bash
# 1. Destroy dev environment
cd capstone-infra/live/dev
terraform destroy -var="region=eu-west-1" -auto-approve

# 2. Destroy staging environment
cd capstone-infra/live/staging
terraform destroy -var="region=eu-west-1" -auto-approve

# 3. Verify no resources left
aws ec2 describe-vpcs --region eu-west-1 --query 'Vpcs[*].VpcId'
aws rds describe-db-instances --region eu-west-1 --query 'DBInstances[*].DBInstanceIdentifier'
aws eks list-clusters --region eu-west-1
aws s3 ls --region eu-west-1 | grep capstone
```

### Manual Cleanup (nếu Terraform state lost)

```bash
# Xóa EKS clusters
aws eks list-clusters --region eu-west-1 --query 'clusters[]'
aws eks delete-cluster --name capstone-dev --region eu-west-1
aws eks delete-cluster --name capstone-staging --region eu-west-1

# Xóa RDS instances
aws rds describe-db-instances --region eu-west-1 \
  --query 'DBInstances[?starts_with(DBInstanceIdentifier, `capstone`)].DBInstanceIdentifier'
aws rds delete-db-instance \
  --db-instance-identifier capstone-db-dev \
  --skip-final-snapshot \
  --region eu-west-1

# Xóa ElastiCache clusters
aws elasticache describe-cache-clusters --region eu-west-1 \
  --query 'CacheClusters[?starts_with(CacheClusterId, `capstone`)].CacheClusterId'
aws elasticache delete-cache-cluster \
  --cache-cluster-id capstone-redis-dev \
  --region eu-west-1

# Xóa ECR repositories
aws ecr describe-repositories --region eu-west-1 \
  --query 'repositories[?starts_with(repositoryName, `capstone`)].repositoryName'
aws ecr delete-repository \
  --repository-name capstone/api-service \
  --force \
  --region eu-west-1

# Xóa S3 buckets (Terraform state + backups)
aws s3api list-buckets --query 'Buckets[?starts_with(Name, `capstone`)].Name'
aws s3 rb s3://capstone-tf-state --force --region eu-west-1
aws s3 rb s3://capstone-db-backups --force --region eu-west-1

# Xóa Route53 hosted zones
aws route53 list-hosted-zones --query 'HostedZones[?contains(Name, `capstone`)].Id'
aws route53 delete-hosted-zone --id ZXXXXXXXXXXXXX

# Xóa NAT Gateways + EIPs
aws ec2 describe-nat-gateways --region eu-west-1 \
  --filter Name=tag:Environment,Values=capstone
aws ec2 release-address --allocation-id eipalloc-xxxxxxxx --region eu-west-1

# Xóa IAM roles (cleanup leftover IRSA roles)
aws iam list-roles --query 'Roles[?starts_with(RoleName, `capstone`)].RoleName'
aws iam delete-role --role-name capstone-api-service-role --region eu-west-1
```

### Budget Alert Setup

```hcl
# Terraform: aws_budgets_budget
resource "aws_budgets_budget" "monthly" {
  name         = "capstone-monthly-limit"
  budget_type  = "COST"
  limit_amount = "200"
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  notification {
    comparison_operator               = "GREATER_THAN"
    threshold                        = 80
    threshold_type                   = "PERCENTAGE"
    notification_type                = "FORECASTED"
    subscriber_email_addresses       = ["thangtm@example.com"]
  }
}
```

---

## H. Environment Strategy Table

| Property | dev | staging | production-like |
|----------|-----|---------|-----------------|
| **ArgoCD Sync** | Auto-sync | Auto-sync | Manual approval |
| **Promotion** | Auto-merge (CI pass) | PR (1 reviewer) | PR (2 approvals + SRE lead) |
| **Review** | None (author only) | 1 team member | SRE + team lead |
| **Terraform apply** | Auto on PR merge | Manual approve | Manual approve (4-eye) |
| **Database** | Local/Helm (dev) | Single-AZ RDS | Multi-AZ RDS |
| **Nodes** | t3.small or kind | t3.medium × 1 | t3.medium × 2 + Spot |
| **Backup** | None | Daily manual | RDS automated daily |
| **Secrets** | ESO local | ESO + ASM dev | ESO + ASM prod |
| **Monitoring** | Basic metrics | Full stack | Full stack + alerting |
| **Feature flags** | All on | All on | Selective |
| **Use case** | Active development | Pre-production test | Production simulation |

---

## I. 10 Anti-Patterns Capstone

| # | Anti-pattern | Hệ quả | Prevention |
|---|-------------|--------|------------|
| 1 | **Scope creep**: thêm 10 service thay vì 3 | Không kịp hoàn thành Day 35 | Stick to: api-service, worker-service, frontend-service |
| 2 | **Không cleanup AWS**: quên `make aws-destroy` | Bill $200-300 sau capstone | Makefile shortcut + budget alert |
| 3 | **Hardcode account ID**: `arn:aws:iam::123456789:role/...` | Không portable, expose account | Dùng variable `data.aws_caller_identity.current.account_id` |
| 4 | **Mix infra + app concerns**: Terraform tạo Kubernetes Secret | App team phải trigger infra pipeline | Repo boundary: infra không biết gì về app |
| 5 | **`latest` image tag**: `image: api:vlatest` | ArgoCD không detect change, drift | Immutable tag: `v1.2.3`, `sha-abc1234f` |
| 6 | **Không backup Terraform state**: local state file | State corruption = infrastructure loss | S3 backend + versioning + DynamoDB lock |
| 7 | **Dùng access key trong GitHub Secrets** | Token leak → crypto mining bill | OIDC trust: GitHub → AWS IAM (no long-lived key) |
| 8 | **Promote bằng `argocd app sync`**: bypass PR | No audit trail, drift Git ≠ cluster | PR promotion only |
| 9 | **Không test destroy flow**: chỉ apply, không destroy | Quên cleanup resources, orphan resources | Test destroy flow trong Day 29 sau khi apply |
| 10 | **Skip ADR**: không ghi lại decision | 6 tháng sau không nhớ tại sao chọn Mode A | Viết ADR trước khi code — Day 28 là bắt buộc |
