import type { DefaultTheme } from "vitepress";
import { createCourseDay } from "./course";

const mbDay = createCourseDay("message-broker");

export const messageBrokerSidebar: DefaultTheme.SidebarItem[] = [
  {
    text: "Message Broker 25 Days",
    items: [
      { text: "Overview", link: "/message-broker/" },
      { text: "Kế hoạch 80/20", link: "/message-broker/" },
    ],
  },
  {
    text: "Phase 1: Messaging Fundamentals + NATS",
    items: [
      mbDay("Day 01 — Fundamentals + NATS Core", "day-01-messaging-fundamentals-and-nats-basics"),
      mbDay("Day 02 — NATS JetStream", "day-02-nats-jetstream"),
      mbDay("Day 03 — NATS Production", "day-03-nats-production"),
    ],
  },
  {
    text: "Phase 2: RabbitMQ",
    items: [
      mbDay("Day 04 — AMQP Protocol", "day-04-amqp-protocol"),
      mbDay("Day 05 — Exchange Types", "day-05-exchange-types"),
      mbDay("Day 06 — Reliability", "day-06-reliability"),
      mbDay("Day 07 — Advanced Patterns", "day-07-advanced-patterns"),
      mbDay("Day 08 — Clustering & HA", "day-08-clustering-ha"),
      mbDay("Day 09 — Performance & Production", "day-09-performance-production"),
    ],
  },
  {
    text: "Phase 3: Kafka",
    items: [
      mbDay("Day 10 — Kafka Fundamentals", "day-10-kafka-fundamentals"),
      mbDay("Day 11 — Producer Internals", "day-11-producer-internals"),
      mbDay("Day 12 — Consumer Internals", "day-12-consumer-internals"),
      mbDay("Day 13 — Replication & ISR", "day-13-replication-isr"),
      mbDay("Day 14 — ZooKeeper vs KRaft", "day-14-zookeeper-vs-kraft"),
      mbDay("Day 15 — Delivery Semantics & Idempotency", "day-15-delivery-semantics-idempotency"),
      mbDay("Day 16 — Schema Management", "day-16-schema-management"),
      mbDay("Day 17 — Kafka Connect & CDC", "day-17-kafka-connect-cdc"),
      mbDay("Day 18 — Kafka Streams Basics", "day-18-kafka-streams-basics"),
      mbDay("Day 19 — Kafka Streams Advanced", "day-19-kafka-streams-advanced"),
      mbDay("Day 20 — Performance Tuning", "day-20-performance-tuning"),
      mbDay("Day 21 — Capacity Planning", "day-21-capacity-planning"),
      mbDay("Day 22 — Security & Multi-tenancy", "day-22-security-multi-tenancy"),
      mbDay("Day 23 — Production Operations", "day-23-production-operations-observability"),
    ],
  },
  {
    text: "Phase 4: Tổng hợp & Capstone",
    items: [
      mbDay("Day 24 — Broker Comparison", "day-24-broker-comparison"),
      mbDay("Day 25 — Capstone Project", "day-25-capstone"),
    ],
  },
];
