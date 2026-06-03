import type { DefaultTheme } from "vitepress";

const COURSE_PATH = "claude-lession";

const claudeDay = (
  text: string,
  slug: string,
): DefaultTheme.SidebarItem => ({
  text,
  collapsed: true,
  items: [
    { text: "Lesson", link: `/${COURSE_PATH}/${slug}/lession` },
    { text: "Document", link: `/${COURSE_PATH}/${slug}/document` },
    { text: "Exercise", link: `/${COURSE_PATH}/${slug}/exercise` },
  ],
});

export const claudeLessionSidebar: DefaultTheme.SidebarItem[] = [
  {
    text: "Claude Code 20 Days",
    items: [
      { text: "Overview", link: "/claude-lession/" },
    ],
  },
  {
    text: "Phase 1: Nền tảng & Agentic Coding (Day 01-04)",
    collapsed: true,
    items: [
      claudeDay("Day 01 — Mindset: Claude Code không phải chatbot", "Day-01"),
      claudeDay("Day 02 — Setup môi trường và workflow cơ bản", "Day-02"),
      claudeDay("Day 03 — Session, context window, resume/continue", "Day-03"),
      claudeDay("Day 04 — Permission modes và an toàn", "Day-04"),
    ],
  },
  {
    text: "Phase 2: Memory & Context Engineering (Day 05-07)",
    collapsed: true,
    items: [
      claudeDay("Day 05 — CLAUDE.md chuẩn cho project", "Day-05"),
      claudeDay("Day 06 — Prompt engineering cho coding task", "Day-06"),
      claudeDay("Day 07 — Khám phá codebase lớn", "Day-07"),
    ],
  },
  {
    text: "Phase 3: Build Feature Thực Tế (Day 08-11)",
    collapsed: true,
    items: [
      claudeDay("Day 08 — Backend CRUD với plan-first workflow", "Day-08"),
      claudeDay("Day 09 — Database migration và data model", "Day-09"),
      claudeDay("Day 10 — Frontend workflow với React", "Day-10"),
      claudeDay("Day 11 — Testing với Claude Code", "Day-11"),
    ],
  },
  {
    text: "Phase 4: Automation (Day 12-15)",
    collapsed: true,
    items: [
      claudeDay("Day 12 — Hooks trong Claude Code", "Day-12"),
      claudeDay("Day 13 — Skills tái sử dụng", "Day-13"),
      claudeDay("Day 14 — Subagents cho workflow chuyên biệt", "Day-14"),
      claudeDay("Day 15 — MCP servers", "Day-15"),
    ],
  },
  {
    text: "Phase 5: Team & Production (Day 16-20)",
    collapsed: true,
    items: [
      claudeDay("Day 16 — GitHub workflow với Claude Code", "Day-16"),
      claudeDay("Day 17 — Refactor legacy code an toàn", "Day-17"),
      claudeDay("Day 18 — Security review và production guardrails", "Day-18"),
      claudeDay("Day 19 — Performance, token, cost, context optimization", "Day-19"),
      claudeDay("Day 20 — Capstone: build feature end-to-end", "Day-20"),
    ],
  },
];
