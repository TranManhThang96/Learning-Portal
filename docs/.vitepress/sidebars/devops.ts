import type { DefaultTheme } from "vitepress";

const devopsDay = (
  text: string,
  slug: string,
): DefaultTheme.SidebarItem => ({
  text,
  collapsed: true,
  items: [
    { text: "Lesson", link: `/devops/${slug}/lesson` },
    { text: "Exercises", link: `/devops/${slug}/exercises` },
    { text: "Document", link: `/devops/${slug}/document` },
  ],
});

export const devopsSidebar: DefaultTheme.SidebarItem[] = [
  {
    text: "DevOps/SRE 50 Days",
    items: [
      { text: "Overview", link: "/devops/" },
      { text: "Course README", link: "/devops/README" },
    ],
  },
  {
    text: "Phase 1: Foundation (Day 01-07)",
    collapsed: false,
    items: [
      devopsDay("Day 01 — DevOps, SRE, Platform Engineering & DORA Metrics", "day-01-devops-sre-platform-engineering"),
      devopsDay("Day 02 — Linux Advanced — Process, Signal, systemd", "day-02-linux-advanced-process-signal-systemd"),
      devopsDay("Day 03 — Linux Networking Fundamentals", "day-03-linux-networking-fundamentals"),
      devopsDay("Day 04 — Linux Performance & Debugging Tools", "day-04-linux-performance-debugging-tools"),
      devopsDay("Day 05 — Bash & Python Automation for DevOps", "day-05-bash-python-automation-devops"),
      devopsDay("Day 06 — Git Workflows & Release Models", "day-06-git-workflows-release-models"),
      devopsDay("Day 07 — Mini-project: Linux + Networking + Automation", "day-07-mini-project-linux-networking-automation"),
    ],
  },
  {
    text: "Phase 2: Docker & Kubernetes Core (Day 08-17)",
    collapsed: true,
    items: [
      devopsDay("Day 08 — Docker Internals — namespace, cgroup, OCI", "day-08-docker-internals-namespace-cgroup-oci"),
      devopsDay("Day 09 — Container Image Optimization & Security", "day-09-container-image-optimization-security"),
      devopsDay("Day 10 — Kubernetes Architecture Deep Dive", "day-10-kubernetes-architecture-deep-dive"),
      devopsDay("Day 11 — Kubernetes Workload Resources", "day-11-kubernetes-workload-resources"),
      devopsDay("Day 12 — Kubernetes Networking Core", "day-12-kubernetes-networking-core"),
      devopsDay("Day 13 — Ingress, Gateway API & Load Balancing", "day-13-ingress-gateway-api-load-balancing"),
      devopsDay("Day 14 — ConfigMap, Secret & External Secret Management", "day-14-configmap-secret-external-secret-management"),
      devopsDay("Day 15 — Storage — PV, PVC, StorageClass, CSI", "day-15-storage-pv-pvc-storageclass-csi"),
      devopsDay("Day 16 — Helm vs Kustomize", "day-16-helm-vs-kustomize"),
      devopsDay("Day 17 — Mini-project: Deploy Microservice Stack on Local K8s", "day-17-mini-project-microservice-stack-local-k8s"),
    ],
  },
  {
    text: "Phase 3: Kubernetes Production (Day 18-25)",
    collapsed: true,
    items: [
      devopsDay("Day 18 — Resource Requests/Limits, QoS, Right-sizing", "day-18-resource-requests-limits-qos-rightsizing"),
      devopsDay("Day 19 — Autoscaling — HPA, VPA, Cluster Autoscaler, KEDA", "day-19-autoscaling-hpa-vpa-cluster-autoscaler-keda"),
      devopsDay("Day 20 — RBAC, Pod Security Standards, NetworkPolicy", "day-20-rbac-pod-security-standards-networkpolicy"),
      devopsDay("Day 21 — Admission Controller, OPA/Gatekeeper, Kyverno", "day-21-admission-controller-opa-gatekeeper-kyverno"),
      devopsDay("Day 22 — Kubernetes Troubleshooting Methodology", "day-22-kubernetes-troubleshooting-methodology"),
      devopsDay("Day 23 — Kubernetes Upgrade, Backup & Node Maintenance", "day-23-kubernetes-upgrade-backup-node-maintenance"),
      devopsDay("Day 24 — Production-ready Kubernetes Checklist", "day-24-production-ready-kubernetes-checklist"),
      devopsDay("Day 25 — Mini-project: Harden, Scale & Debug K8s App", "day-25-kubernetes-production-hardening-mini-project"),
    ],
  },
  {
    text: "Phase 4: IaC & GitOps (Day 26-31)",
    collapsed: true,
    items: [
      devopsDay("Day 26 — Infrastructure as Code Principles", "day-26-infrastructure-as-code-principles"),
      devopsDay("Day 27 — Terraform Fundamentals", "day-27-terraform-fundamentals"),
      devopsDay("Day 28 — Terraform Advanced — Remote State, Modules, Drift", "day-28-terraform-advanced-remote-state-modules-drift"),
      devopsDay("Day 29 — Pulumi vs Terraform vs CDK", "day-29-pulumi-vs-terraform-vs-cdk"),
      devopsDay("Day 30 — Ansible for Configuration Management", "day-30-ansible-configuration-management"),
      devopsDay("Day 31 — GitOps with ArgoCD & Flux", "day-31-gitops-argocd-flux"),
    ],
  },
  {
    text: "Phase 5: CI/CD & Release Engineering (Day 32-37)",
    collapsed: true,
    items: [
      devopsDay("Day 32 — CI/CD Design Patterns", "day-32-cicd-design-patterns"),
      devopsDay("Day 33 — GitHub Actions Deep Dive", "day-33-github-actions-deep-dive"),
      devopsDay("Day 34 — GitLab CI, Jenkins, CircleCI Comparison", "day-34-gitlab-ci-jenkins-circleci-comparison"),
      devopsDay("Day 35 — Deployment Strategies — Rolling, Blue-Green, Canary", "day-35-deployment-strategies-rolling-bluegreen-canary"),
      devopsDay("Day 36 — Progressive Delivery with Argo Rollouts / Flagger", "day-36-progressive-delivery-argo-rollouts-flagger"),
      devopsDay("Day 37 — Artifact Registry, Image Signing & Supply Chain", "day-37-artifact-registry-image-signing-supply-chain"),
    ],
  },
  {
    text: "Phase 6: Observability & Reliability (Day 38-44)",
    collapsed: true,
    items: [
      devopsDay("Day 38 — Observability — Metrics, Logs, Traces", "day-38-observability-metrics-logs-traces"),
      devopsDay("Day 39 — Prometheus & PromQL", "day-39-prometheus-promql"),
      devopsDay("Day 40 — Grafana Dashboard & Alerting", "day-40-grafana-dashboard-alerting"),
      devopsDay("Day 41 — Logging Architecture — Loki vs ELK vs Splunk", "day-41-logging-architecture-loki-elk-splunk"),
      devopsDay("Day 42 — OpenTelemetry & Distributed Tracing", "day-42-opentelemetry-distributed-tracing"),
      devopsDay("Day 43 — SLI/SLO, Error Budget & Alert Fatigue", "day-43-sli-slo-error-budget-alert-fatigue"),
      devopsDay("Day 44 — Incident Response & Postmortem", "day-44-incident-response-postmortem"),
    ],
  },
  {
    text: "Phase 7: Security, Cost, DR & Capstone (Day 45-50)",
    collapsed: true,
    items: [
      devopsDay("Day 45 — DevSecOps — SAST, DAST, SCA, Secret Scanning", "day-45-devsecops-sast-dast-sca-secret-scanning"),
      devopsDay("Day 46 — Service Mesh & Zero-trust Overview", "day-46-service-mesh-zero-trust-overview"),
      devopsDay("Day 47 — Database on Kubernetes vs Managed Database", "day-47-database-kubernetes-vs-managed"),
      devopsDay("Day 48 — Multi-region, Disaster Recovery, RPO/RTO", "day-48-multi-region-disaster-recovery-rpo-rto"),
      devopsDay("Day 49 — Cost Optimization & FinOps", "day-49-cost-optimization-finops"),
      devopsDay("Day 50 — Capstone: Production Platform Design", "day-50-capstone-production-platform-design"),
    ],
  },
];
