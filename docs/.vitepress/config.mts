import { defineConfig } from "vitepress";
import { pythonSidebar } from "./sidebars/python";

// https://vitepress.dev/reference/site-config
export default defineConfig({
  title: "Learning Portal",
  description:
    "Lộ trình học lập trình, backend, data, DevOps và AI theo nhịp thực chiến",
  head: [
    ["link", { rel: "icon", type: "image/svg+xml", href: "/favicon.svg" }],
    ["link", { rel: "shortcut icon", href: "/favicon.ico" }],
  ],
  ignoreDeadLinks: "localhostLinks",
  themeConfig: {
    // https://vitepress.dev/reference/default-theme-config
    siteTitle: "Learning Portal",
    nav: [
      { text: "Home", link: "/" },
      {
        text: "Backend",
        items: [
          { text: "Backend Advanced", link: "/backend-advanced/" },
          { text: "Redis", link: "/redis/" },
          { text: "Message Broker", link: "/message-broker/" },
          { text: "SQL", link: "/sql/" },
          { text: "Solution Architect", link: "/solution-architect/" },
          { text: "Design Pattern", link: "/solid-design-pattern/" },
          { text: "Unit Test", link: "/unit-test/" },
        ],
      },
      {
        text: "Infrastructure",
        items: [
          { text: "DevOps", link: "/devops/" },
          { text: "AWS", link: "/aws/" },
          { text: "Docker", link: "/docker/" },
          { text: "Kubernetes (K3s/K8s)", link: "/k3s-k8s/" },
          { text: "Linux", link: "/linux/" },
          { text: "CI/CD", link: "/jenkins-github_action-gitlab_cicd/" },
          { text: "Monitoring", link: "/loki-grafana-prometheus/" },
          { text: "ELK Stack", link: "/elasticsearch-logstash-kibana/" },
          { text: "Nginx & Gateway", link: "/gateway-lb-nginx/" },
          { text: "IaC", link: "/terraform-ansible-argoCD/" },
        ],
      },
      {
        text: "Languages",
        items: [
          { text: "Go", link: "/go/" },
          { text: "Java", link: "/java/" },
          { text: "Python", link: "/python/" },
          { text: "Rust", link: "/rust/" },
        ],
      },
      {
        text: "More",
        items: [
          { text: "AI Engineer", link: "/ai-engineer/" },
          { text: "DSA", link: "/dsa/" },
          { text: "Frontend", link: "/frontend/" },
          { text: "Security", link: "/security-develop/" },
          { text: "Web3", link: "/web3-solidity/" },
          { text: "Git", link: "/git/" },
          { text: "Obsidian", link: "/obsidian/" },
          { text: "Investment", link: "/dau-tu/" },
          { text: "MMO", link: "/mmo/" },
          { text: "Manager with AI", link: "/manager-with-ai/" },
        ],
      },
    ],

    sidebar: {
      "/python/": pythonSidebar,
      "/redis/": [
        {
          text: "Redis Learning Plan",
          items: [
            { text: "Overview", link: "/redis/" },
            {
              text: "Lộ trình 30 ngày",
              link: "/redis/redis-learning-plan/README.md",
            },
            {
              text: "Day 01 - Architecture",
              link: "/redis/redis-learning-plan/day-01-redis-architecture-and-use-cases/lesson.md",
            },
            {
              text: "Document Day 01",
              link: "/redis/redis-learning-plan/day-01-redis-architecture-and-use-cases/document.md",
            },
          ],
        },
      ],
    },
    search: {
      provider: "local",
    },
    socialLinks: [
      { icon: "github", link: "https://github.com/TranManhThang96/" },
    ],
  },
});
