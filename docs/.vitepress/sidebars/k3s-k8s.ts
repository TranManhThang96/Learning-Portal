import type { DefaultTheme } from "vitepress";

const COURSE_BASE = "/k3s-k8s/k8s-learning-journey-45-days";

const k3sDay = (
  text: string,
  slug: string,
): DefaultTheme.SidebarItem => ({
  text,
  collapsed: true,
  items: [
    { text: "Lesson", link: `${COURSE_BASE}/${slug}/lesson` },
    { text: "Document", link: `${COURSE_BASE}/${slug}/document` },
    { text: "Exercises", link: `${COURSE_BASE}/${slug}/exercises` },
  ],
});

export const k3sK8sSidebar: DefaultTheme.SidebarItem[] = [
  {
    text: "K8s/K3s 45 Days",
    items: [
      { text: "Overview", link: "/k3s-k8s/" },
      { text: "Course README", link: `${COURSE_BASE}/README` },
    ],
  },
  {
    text: "Phase 1: Nền tảng & K3s Setup (Day 01-04)",
    collapsed: false,
    items: [
      k3sDay("Day 01 — Mental Model & Runtime Refresher", "day-01-kubernetes-mental-model-and-runtime-refresher"),
      k3sDay("Day 02 — Architecture Overview", "day-02-kubernetes-architecture-overview"),
      k3sDay("Day 03 — K3s vs K8s vs Distros", "day-03-k3s-vs-kubernetes-microk8s-minikube-kind"),
      k3sDay("Day 04 — K3s Local Install (Single/Multi Node)", "day-04-k3s-local-single-node-and-multi-node-installation"),
      { text: "Phase 1 Summary", link: `${COURSE_BASE}/phase-1-summary` },
    ],
  },
  {
    text: "Phase 2: Core Workloads & Config (Day 05-14)",
    collapsed: true,
    items: [
      k3sDay("Day 05 — Control Plane Deep Dive", "day-05-control-plane-deep-dive"),
      k3sDay("Day 06 — Worker Node Deep Dive", "day-06-worker-node-deep-dive"),
      k3sDay("Day 07 — kubectl Mastery", "day-07-kubectl-mastery-and-resource-inspection"),
      k3sDay("Day 08 — Pod Lifecycle & Multi-container", "day-08-pod-lifecycle-and-multi-container-patterns"),
      k3sDay("Day 09 — ReplicaSet & Deployment", "day-09-replicaset-and-deployment"),
      k3sDay("Day 10 — StatefulSet", "day-10-statefulset"),
      k3sDay("Day 11 — DaemonSet", "day-11-daemonset"),
      k3sDay("Day 12 — Job & CronJob", "day-12-job-and-cronjob"),
      k3sDay("Day 13 — ConfigMap, Secret & Secret Management", "day-13-configmap-secret-and-practical-secret-management"),
      k3sDay("Day 14 — Namespace, Labels, Selectors", "day-14-namespace-labels-selectors-annotations"),
      { text: "Phase 2 Summary", link: `${COURSE_BASE}/phase-2-summary` },
    ],
  },
  {
    text: "Phase 3: Networking & Traffic (Day 15-21)",
    collapsed: true,
    items: [
      k3sDay("Day 15 — Service Types", "day-15-service-types"),
      k3sDay("Day 16 — kube-proxy Modes", "day-16-kube-proxy-modes"),
      k3sDay("Day 17 — Ingress & Controllers", "day-17-ingress-and-ingress-controllers"),
      k3sDay("Day 18 — DNS in Kubernetes", "day-18-dns-in-kubernetes"),
      k3sDay("Day 19 — Network Policies", "day-19-network-policies"),
      k3sDay("Day 20 — CNI Deep Dive", "day-20-cni-deep-dive"),
      k3sDay("Day 21 — Service Mesh Intro", "day-21-service-mesh-introduction"),
      { text: "Phase 3 Summary", link: `${COURSE_BASE}/phase-3-summary` },
    ],
  },
  {
    text: "Phase 4: Storage & Stateful Apps (Day 22-28)",
    collapsed: true,
    items: [
      k3sDay("Day 22 — Volumes", "day-22-volumes"),
      k3sDay("Day 23 — PV & PVC", "day-23-persistentvolume-and-persistentvolumeclaim"),
      k3sDay("Day 24 — StorageClass & Dynamic Provisioning", "day-24-storageclass-and-dynamic-provisioning"),
      k3sDay("Day 25 — CSI Drivers & Troubleshooting", "day-25-csi-drivers-and-storage-troubleshooting"),
      k3sDay("Day 26 — PostgreSQL on K8s", "day-26-postgresql-on-kubernetes"),
      k3sDay("Day 27 — Redis on K8s", "day-27-redis-on-kubernetes"),
      k3sDay("Day 28 — Kafka on K8s", "day-28-kafka-on-kubernetes"),
      { text: "Phase 4 Summary", link: `${COURSE_BASE}/phase-4-summary` },
    ],
  },
  {
    text: "Phase 5: Observability & Security (Day 29-35)",
    collapsed: true,
    items: [
      k3sDay("Day 29 — Logging", "day-29-logging"),
      k3sDay("Day 30 — Monitoring", "day-30-monitoring"),
      k3sDay("Day 31 — Distributed Tracing", "day-31-distributed-tracing"),
      k3sDay("Day 32 — Debugging Toolkit", "day-32-kubernetes-debugging-toolkit"),
      k3sDay("Day 33 — Resource Debugging & Failure", "day-33-resource-debugging-and-failure-scenarios"),
      k3sDay("Day 34 — RBAC, k9s, Lens", "day-34-rbac-k9s-lens-operations"),
      k3sDay("Day 35 — Pod Security & Admission", "day-35-pod-security-and-admission-control"),
      { text: "Phase 5 Summary", link: `${COURSE_BASE}/phase-5-summary` },
    ],
  },
  {
    text: "Phase 6: Advanced, GitOps & Capstone (Day 36-45)",
    collapsed: true,
    items: [
      k3sDay("Day 36 — Helm Fundamentals", "day-36-helm-fundamentals"),
      k3sDay("Day 37 — Helm Chart for Microservices", "day-37-helm-chart-for-microservices"),
      k3sDay("Day 38 — CRD & Operator Pattern", "day-38-crd-and-operator-pattern"),
      k3sDay("Day 39 — Autoscaling", "day-39-autoscaling"),
      k3sDay("Day 40 — Advanced Scheduling", "day-40-advanced-scheduling"),
      k3sDay("Day 41 — CI/CD GitOps with ArgoCD", "day-41-cicd-gitops-with-argocd"),
      k3sDay("Day 42 — Backup, Restore, DR", "day-42-backup-restore-disaster-recovery"),
      k3sDay("Day 43 — Managed K8s Production Readiness", "day-43-managed-kubernetes-production-readiness"),
      k3sDay("Day 44 — Capstone Part 1", "day-44-capstone-project-part-1"),
      k3sDay("Day 45 — Capstone Part 2", "day-45-capstone-project-part-2"),
      { text: "Phase 6 Summary", link: `${COURSE_BASE}/phase-6-summary` },
    ],
  },
];
