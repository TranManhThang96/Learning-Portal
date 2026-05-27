import type { DefaultTheme } from "vitepress";
import { createCourseDay } from "./course";

const pythonDay = createCourseDay("python");

export const pythonSidebar: DefaultTheme.SidebarItem[] = [
  {
    text: "Python 35 Days",
    items: [
      { text: "Overview", link: "/python/" },
      {
        text: "Bẫy python nên học sớm",
        link: "/python/day1000-bay-python-nen-hoc-som",
      },
    ],
  },
  {
    text: "Python Core",
    items: [
      pythonDay("Day 01 - Môi trường & Tooling", "day01-moi-truong-va-tooling"),
      pythonDay("Day 02 - Cú pháp cơ bản", "day02-cu-phap-python-co-ban"),
      pythonDay("Day 03 - Cấu trúc dữ liệu", "day03-cau-truc-du-lieu"),
      pythonDay("Day 04 - Hàm nâng cao", "day04-ham-nang-cao"),
      pythonDay("Day 05 - OOP trong Python", "day05-oop-trong-python"),
      pythonDay(
        "Day 06 - Modules & Packages",
        "day06-modules-packages-cau-truc-du-an",
      ),
      pythonDay("Day 07 - Xử lý lỗi & Typing", "day07-xu-ly-loi-va-typing"),
      pythonDay(
        "Day 08 - File & Serialization",
        "day08-doc-ghi-file-context-managers-serialization",
      ),
      pythonDay("Day 09 - Async Python", "day09-async-python-bat-dong-bo"),
      pythonDay(
        "Day 10 - Concurrency & Parallelism",
        "day10-dong-thoi-va-song-song",
      ),
      pythonDay("Day 11 - Pytest", "day11-kiem-thu-voi-pytest"),
      pythonDay(
        "Day 12 - Database với Python",
        "day12-co-so-du-lieu-voi-python",
      ),
    ],
  },
  {
    text: "Backend & Data",
    items: [
      pythonDay("Day 13 - FastAPI cơ bản", "day13-fastapi-co-ban"),
      pythonDay("Day 14 - FastAPI nâng cao", "day14-fastapi-nang-cao"),
      pythonDay(
        "Day 15 - FastAPI Database Caching",
        "day15-fastapi-database-caching",
      ),
      pythonDay("Day 16 - Production", "day16-trien-khai-san-sang-production"),
      pythonDay("Day 17 - NumPy/Pandas", "day17-numpy-pandas-cho-data-ai"),
      pythonDay("Day 18 - OpenAI SDK & LLM", "day18-openai-sdk-va-llm-co-ban"),
    ],
  },
  {
    text: "AI Engineering",
    items: [
      pythonDay("Day 19 - Prompt Engineering", "day19-ky-thuat-viet-prompt"),
      pythonDay("Day 20 - LangChain", "day20-langchain-chuoi-cong-cu-agents"),
      pythonDay("Day 21 - RAG", "day21-rag-truy-xuat-tang-cuong"),
      pythonDay("Day 22 - RAG nâng cao", "day22-rag-nang-cao-toi-uu"),
      pythonDay("Day 23 - LlamaIndex", "day23-llamaindex"),
      pythonDay("Day 24 - LangGraph", "day24-langgraph-luong-cong-viec-agent"),
      pythonDay("Day 25 - Multi-Agent", "day25-he-thong-da-agent"),
      pythonDay("Day 26 - Hugging Face", "day26-huggingface-va-mo-hinh-cuc-bo"),
      pythonDay("Day 27 - Fine-tuning", "day27-tinh-chinh-va-tuy-bien-mo-hinh"),
      pythonDay("Day 28 - AI API Integration", "day28-api-ai-va-tich-hop"),
      pythonDay("Day 29 - AI Production", "day29-he-thong-ai-production"),
      pythonDay("Day 30 - AI System Design", "day30-thiet-ke-he-thong-ai"),
    ],
  },
  {
    text: "Review & Projects",
    items: [
      pythonDay(
        "Day 31 - Review Python/FastAPI",
        "day31-on-tap-python-core-fastapi",
      ),
      pythonDay("Day 32 - Review AI/LLM Stack", "day32-on-tap-ai-llm-stack"),
      pythonDay(
        "Day 33 - AI Backend Service",
        "day33-project-ai-backend-service",
      ),
      pythonDay("Day 34 - Agentic System", "day34-project-agentic-system"),
      pythonDay("Day 35 - Roadmap Review", "day35-review-tong-the-roadmap"),
    ],
  },
];
