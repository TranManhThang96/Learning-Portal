import type { DefaultTheme } from "vitepress";

const gwDay = (
  text: string,
  slug: string,
): DefaultTheme.SidebarItem => ({
  text,
  collapsed: true,
  items: [
    { text: "Lesson", link: `/gateway-lb-nginx/${slug}/lesson` },
    { text: "Exercises", link: `/gateway-lb-nginx/${slug}/exercises` },
    { text: "Document", link: `/gateway-lb-nginx/${slug}/document` },
  ],
});

export const gatewayLbNginxSidebar: DefaultTheme.SidebarItem[] = [
  {
    text: "Nginx & Kong Gateway 21 Days",
    items: [
      { text: "Overview", link: "/gateway-lb-nginx/" },
      { text: "Course README", link: "/gateway-lb-nginx/README" },
    ],
  },
  {
    text: "Week 1: Nginx & Load Balancing Foundation",
    collapsed: false,
    items: [
      gwDay("Day 01 — Reverse Proxy & Traffic Flow", "day-01-reverse-proxy-traffic-flow"),
      gwDay("Day 02 — Nginx Architecture: Master/Worker, Event Loop", "day-02-nginx-architecture"),
      gwDay("Day 03 — Load Balancing Algorithms", "day-03-load-balancing-algorithms"),
      gwDay("Day 04 — Health Check, Failover & Upstream Failure", "day-04-health-check-failover"),
      gwDay("Day 05 — TLS Termination, HTTP/2 & Secure Edge", "day-05-tls-http2-secure-edge"),
      gwDay("Day 06 — Rate Limiting, Connection Limiting & Protection", "day-06-rate-limiting"),
      gwDay("Day 07 — Nginx Performance Tuning & Benchmark", "day-07-nginx-performance"),
    ],
  },
  {
    text: "Week 2: Kong Gateway Core & Traffic Management",
    collapsed: true,
    items: [
      gwDay("Day 08 — Kong Architecture & OpenResty Foundation", "day-08-kong-architecture"),
      gwDay("Day 09 — Kong Core Entities: Services, Routes, Consumers, Plugins", "day-09-kong-core-entities"),
      gwDay("Day 10 — DB-less vs DB-mode & decK Workflow", "day-10-kong-dbless-deck"),
      gwDay("Day 11 — Authentication: Key Auth, JWT, mTLS", "day-11-kong-authentication"),
      gwDay("Day 12 — Rate Limiting, ACL, IP Restriction & Request Control", "day-12-kong-traffic-control"),
      gwDay("Day 13 — Kong Upstream: Load Balancing & Health Checks", "day-13-kong-upstream"),
      gwDay("Day 14 — Timeout, Retry, Circuit Breaker & Backpressure", "day-14-kong-resilience"),
      gwDay("Day 15 — Canary, Blue-Green & Gateway Config Rollback", "day-15-kong-rollout"),
    ],
  },
  {
    text: "Week 3: Observability, Service Discovery & Production",
    collapsed: true,
    items: [
      gwDay("Day 16 — Observability for Nginx & Kong", "day-16-observability-nginx-kong"),
      gwDay("Day 17 — Consul Service Discovery Essentials", "day-17-consul-service-discovery"),
      gwDay("Day 18 — Nginx/Kong + Service Discovery Integration", "day-18-nginx-kong-service-discovery"),
      gwDay("Day 19 — Production Security Hardening", "day-19-production-security-hardening"),
      gwDay("Day 20 — Capstone: End-to-End Gateway System", "day-20-capstone-gateway-system"),
      gwDay("Day 21 — Failure Testing, Benchmark & Final Review", "day-21-failure-testing-final-review"),
    ],
  },
];
