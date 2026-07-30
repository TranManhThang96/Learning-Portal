import type { DefaultTheme } from "vitepress";

const COURSE_BASE = "/learn-fast/kubernetes";

const k8sDay = (
  text: string,
  slug: string,
): DefaultTheme.SidebarItem => ({
  text,
  collapsed: true,
  items: [
    { text: "Bài học", link: `${COURSE_BASE}/${slug}/bai-hoc` },
    { text: "Thực hành", link: `${COURSE_BASE}/${slug}/thuc-hanh` },
    { text: "Tài liệu", link: `${COURSE_BASE}/${slug}/tai-lieu` },
  ],
});

export const kubernetesSidebar: DefaultTheme.SidebarItem[] = [
  {
    text: "Kubernetes 7 ngày",
    items: [
      { text: "Tổng quan", link: `${COURSE_BASE}/` },
      { text: "Giới thiệu & Roadmap", link: `${COURSE_BASE}/00-gioi-thieu` },
      { text: "Tổng hợp & Ôn tập", link: `${COURSE_BASE}/99-tong-hop` },
    ],
  },
  {
    text: "Nền tảng (Ngày 1-2)",
    collapsed: false,
    items: [
      k8sDay("Ngày 1 — K8s Core & Minikube", "ngay-01-k8s-core-minikube"),
      k8sDay("Ngày 2 — Production Readiness & Redis", "ngay-02-production-readiness-redis"),
    ],
  },
  {
    text: "Đóng gói & Triển khai (Ngày 3-4)",
    collapsed: true,
    items: [
      k8sDay("Ngày 3 — Helm", "ngay-03-helm"),
      k8sDay("Ngày 4 — GitOps & Argo CD", "ngay-04-gitops-argocd"),
    ],
  },
  {
    text: "Hạ tầng & Quan sát (Ngày 5-6)",
    collapsed: true,
    items: [
      k8sDay("Ngày 5 — Terraform & Floci", "ngay-05-terraform-floci"),
      k8sDay("Ngày 6 — Observability", "ngay-06-observability-prometheus-grafana-elk"),
    ],
  },
  {
    text: "Capstone (Ngày 7)",
    collapsed: true,
    items: [
      k8sDay("Ngày 7 — System Design", "ngay-07-capstone-system-design"),
    ],
  },
];
