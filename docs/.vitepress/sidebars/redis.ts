import type { DefaultTheme } from "vitepress";

const redisDay = (
  text: string,
  slug: string,
): DefaultTheme.SidebarItem => ({
  text,
  collapsed: true,
  items: [
    { text: "Lesson", link: `/redis/redis-learning-plan/${slug}/lesson` },
    { text: "Document", link: `/redis/redis-learning-plan/${slug}/document` },
    { text: "Exercises", link: `/redis/redis-learning-plan/${slug}/exercises` },
  ],
});

export const redisSidebar: DefaultTheme.SidebarItem[] = [
  {
    text: "Redis 30 Days",
    items: [
      { text: "Overview", link: "/redis/" },
      { text: "Course README", link: "/redis/redis-learning-plan/README" },
    ],
  },
  {
    text: "Phase 1: Foundation & Data Structures (Day 01-05)",
    collapsed: true,
    items: [
      redisDay("Day 01 — Redis Architecture & Production Use Cases", "day-01-redis-architecture-and-use-cases"),
      redisDay("Day 02 — Core Data Structures", "day-02-core-data-structures"),
      redisDay("Day 03 — Advanced Data Structures", "day-03-advanced-data-structures"),
      redisDay("Day 04 — Key Design & Data Modeling", "day-04-key-design-and-data-modeling"),
      redisDay("Day 05 — Encoding Internals & Memory Footprint", "day-05-encoding-internals-and-memory-footprint"),
    ],
  },
  {
    text: "Phase 2: Persistence, Memory & Capacity (Day 06-10)",
    collapsed: true,
    items: [
      redisDay("Day 06 — Persistence RDB & AOF", "day-06-persistence-rdb-aof"),
      redisDay("Day 07 — AOF Rewrite & Durability Trade-off", "day-07-aof-rewrite-and-durability-tradeoff"),
      redisDay("Day 08 — Memory Management & Eviction", "day-08-memory-management-and-eviction"),
      redisDay("Day 09 — Memory Optimization & Fragmentation", "day-09-memory-optimization-and-fragmentation"),
      redisDay("Day 10 — Capacity Planning Basics", "day-10-capacity-planning-basics"),
    ],
  },
  {
    text: "Phase 3: Performance Engineering (Day 11-14)",
    collapsed: true,
    items: [
      redisDay("Day 11 — Pipelining & Batching", "day-11-pipelining-and-batching"),
      redisDay("Day 12 — Connection Pooling & Client Behavior", "day-12-connection-pooling-and-client-behavior"),
      redisDay("Day 13 — Latency Analysis & Benchmarking", "day-13-latency-analysis-and-benchmarking"),
      redisDay("Day 14 — Hot Key & Big Key Problems", "day-14-hot-key-and-big-key-problems"),
    ],
  },
  {
    text: "Phase 4: Atomicity, Scripting & Messaging (Day 15-18)",
    collapsed: true,
    items: [
      redisDay("Day 15 — Transactions, WATCH & Atomicity", "day-15-transactions-watch-and-atomicity"),
      redisDay("Day 16 — Lua Scripting & Redis Functions", "day-16-lua-scripting-and-redis-functions"),
      redisDay("Day 17 — Pub/Sub Patterns & Limitations", "day-17-pubsub-patterns-and-limitations"),
      redisDay("Day 18 — Redis Streams & Consumer Groups", "day-18-redis-streams-and-consumer-groups"),
    ],
  },
  {
    text: "Phase 5: High Availability & Cluster (Day 19-24)",
    collapsed: true,
    items: [
      redisDay("Day 19 — Replication Internals", "day-19-replication-internals"),
      redisDay("Day 20 — Sentinel & High Availability", "day-20-sentinel-and-high-availability"),
      redisDay("Day 21 — Failover, Client Retry & Chaos Lab", "day-21-failover-client-retry-and-chaos-lab"),
      redisDay("Day 22 — Redis Cluster & Hash Slots", "day-22-redis-cluster-and-hash-slots"),
      redisDay("Day 23 — Sharding Strategies & Key Distribution", "day-23-sharding-strategies-and-key-distribution"),
      redisDay("Day 24 — Cluster Operations & Resharding", "day-24-cluster-operations-and-resharding"),
    ],
  },
  {
    text: "Phase 6: Production Patterns (Day 25-28)",
    collapsed: true,
    items: [
      redisDay("Day 25 — Caching Patterns & Consistency", "day-25-caching-patterns-and-consistency"),
      redisDay("Day 26 — Cache Stampede & Thundering Herd", "day-26-cache-stampede-and-thundering-herd"),
      redisDay("Day 27 — Rate Limiting, Session & Leaderboard", "day-27-rate-limiting-session-leaderboard-patterns"),
      redisDay("Day 28 — Distributed Locking & Coordination", "day-28-distributed-locking-and-coordination"),
    ],
  },
  {
    text: "Phase 7: Observability & Capstone (Day 29-30)",
    collapsed: true,
    items: [
      redisDay("Day 29 — Observability, Security & Troubleshooting", "day-29-observability-security-and-troubleshooting"),
      redisDay("Day 30 — Capstone: Production Redis Architecture", "day-30-capstone-production-redis-architecture"),
    ],
  },
];
