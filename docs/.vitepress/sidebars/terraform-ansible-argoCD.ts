import type { DefaultTheme } from "vitepress";

const courseDay = (
  text: string,
  slug: string,
): DefaultTheme.SidebarItem => ({
  text,
  collapsed: true,
  items: [
    { text: "Lesson", link: `/terraform-ansible-argoCD/${slug}/lesson` },
    { text: "Resources", link: `/terraform-ansible-argoCD/${slug}/document` },
    { text: "Exercises", link: `/terraform-ansible-argoCD/${slug}/exercises` },
  ],
});

export const terraformAnsibleArgoCDSidebar: DefaultTheme.SidebarItem[] = [
  {
    text: "Terraform + Ansible + ArgoCD 35 Days",
    items: [
      { text: "Overview", link: "/terraform-ansible-argoCD/" },
      { text: "Week 1 README", link: "/terraform-ansible-argoCD/week-1-terraform-foundations/README" },
      { text: "Week 2 README", link: "/terraform-ansible-argoCD/week-2-terraform-production/README" },
      { text: "Week 3 README", link: "/terraform-ansible-argoCD/week-3-ansible-argocd-core/README" },
      { text: "Week 4 README", link: "/terraform-ansible-argoCD/week-4-argocd-advanced/README" },
      { text: "Week 5 README", link: "/terraform-ansible-argoCD/week-5-capstone/README" },
    ],
  },
  {
    text: "Phase 1: Terraform Foundations (Day 1-6)",
    collapsed: false,
    items: [
      courseDay("Day 01 — IaC Foundations & Terraform Mental Model", "week-1-terraform-foundations/day-01-iac-foundations"),
      courseDay("Day 02 — HCL, Variables, Outputs, Locals", "week-1-terraform-foundations/day-02-hcl-variables-outputs"),
      courseDay("Day 03 — Providers, Resources, Data Sources", "week-1-terraform-foundations/day-03-providers-resources-data-sources"),
      courseDay("Day 04 — Terraform State Fundamentals", "week-1-terraform-foundations/day-04-terraform-state-fundamentals"),
      courseDay("Day 05 — Remote Backend with S3 + DynamoDB", "week-1-terraform-foundations/day-05-remote-backend"),
      courseDay("Day 06 — Terraform Module Basics", "week-1-terraform-foundations/day-06-module-basics"),
    ],
  },
  {
    text: "Phase 2: Terraform Production (Day 7-12)",
    collapsed: true,
    items: [
      courseDay("Day 07 — Module Design for Production", "week-2-terraform-production/day-07-module-design-production"),
      courseDay("Day 08 — Multi-Environment Strategy", "week-2-terraform-production/day-08-multi-environment"),
      courseDay("Day 09 — Advanced HCL: for_each, count, dynamic", "week-2-terraform-production/day-09-advanced-hcl"),
      courseDay("Day 10 — Lifecycle, Import, Moved Blocks", "week-2-terraform-production/day-10-import-refactor-lifecycle"),
      courseDay("Day 11 — Terraform CI/CD, OIDC, Quality Gates", "week-2-terraform-production/day-11-terraform-cicd-quality-gates"),
      courseDay("Day 12 — State, Drift Detection, Cost, Policy", "week-2-terraform-production/day-12-state-drift-cost-policy"),
    ],
  },
  {
    text: "Phase 3: Ansible & ArgoCD Core (Day 13-19)",
    collapsed: true,
    items: [
      courseDay("Day 13 — Ansible Mental Model & Idempotency", "week-3-ansible-argocd-core/day-13-ansible-mental-model"),
      courseDay("Day 14 — Variables, Facts, Conditionals, Handlers", "week-3-ansible-argocd-core/day-14-ansible-variables-handlers"),
      courseDay("Day 15 — Roles, Vault, Dynamic Inventory", "week-3-ansible-argocd-core/day-15-ansible-roles-vault-inventory"),
      courseDay("Day 16 — Terraform + Ansible Integration", "week-3-ansible-argocd-core/day-16-terraform-ansible-integration"),
      courseDay("Day 17 — GitOps Principles & ArgoCD Architecture", "week-3-ansible-argocd-core/day-17-gitops-argocd-architecture"),
      courseDay("Day 18 — Application, AppProject, Sync Policy", "week-3-ansible-argocd-core/day-18-argocd-application-project-sync"),
      courseDay("Day 19 — Helm, Kustomize, Overlays với ArgoCD", "week-3-ansible-argocd-core/day-19-helm-kustomize-argocd"),
    ],
  },
  {
    text: "Phase 4: ArgoCD Advanced (Day 20-27)",
    collapsed: true,
    items: [
      courseDay("Day 20 — GitOps Repo Structure", "week-4-argocd-advanced/day-20-gitops-repo-structure"),
      courseDay("Day 21 — App of Apps Pattern", "week-4-argocd-advanced/day-21-app-of-apps"),
      courseDay("Day 22 — ApplicationSet Basics", "week-4-argocd-advanced/day-22-applicationset-basics"),
      courseDay("Day 23 — ApplicationSet Advanced", "week-4-argocd-advanced/day-23-applicationset-advanced"),
      courseDay("Day 24 — Sync Waves, Hooks, Dependencies", "week-4-argocd-advanced/day-24-sync-waves-hooks"),
      courseDay("Day 25 — Secrets Management, RBAC, SSO", "week-4-argocd-advanced/day-25-secrets-rbac-sso"),
      courseDay("Day 26 — Argo Rollouts, Progressive Delivery", "week-4-argocd-advanced/day-26-argo-rollouts"),
      courseDay("Day 27 — ArgoCD Observability, Notifications, DR", "week-4-argocd-advanced/day-27-argocd-observability-dr"),
    ],
  },
  {
    text: "Phase 5: Capstone Production-Grade (Day 28-35)",
    collapsed: true,
    items: [
      courseDay("Day 28 — Capstone Architecture & Strategy", "week-5-capstone/day-28-capstone-architecture"),
      courseDay("Day 29 — Infrastructure Network Layer", "week-5-capstone/day-29-infra-network-layer"),
      courseDay("Day 30 — Kubernetes & IAM Layer", "week-5-capstone/day-30-kubernetes-iam-layer"),
      courseDay("Day 31 — Data Layer: PostgreSQL, Redis, Secrets", "week-5-capstone/day-31-data-layer-secrets"),
      courseDay("Day 32 — Platform Bootstrap Layer", "week-5-capstone/day-32-platform-bootstrap"),
      courseDay("Day 33 — GitOps Apps Layer & Promotion", "week-5-capstone/day-33-gitops-apps-promotion"),
      courseDay("Day 34 — CI/CD, Observability, Reliability", "week-5-capstone/day-34-cicd-observability-reliability"),
      courseDay("Day 35 — Disaster Recovery, Final Demo, Runbook", "week-5-capstone/day-35-disaster-recovery-demo"),
    ],
  },
];
