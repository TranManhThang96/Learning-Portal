# Claude Code Practical Course — 20 ngày thực hành agentic coding

Lộ trình dành cho developer mid-level đến senior muốn dùng Claude Code như một **agentic terminal tool** trong công việc thật, vẫn kiểm soát chất lượng, security, maintainability và chi phí context. Khóa học không xem Claude Code như chatbot mà là một pair engineer có khả năng đọc codebase, lập kế hoạch, sửa code, viết test, review diff và hỗ trợ Git workflow.

## Bắt đầu nhanh (80/20)

Nếu chỉ có thời gian hạn chế, học theo thứ tự sau để nhanh nhất có thể dùng Claude Code trong repo thật:

1. [Day 01: Mindset — Claude Code không phải chatbot](./Day-01/lession) — hiểu agentic coding khác chatbot thế nào, vòng lặp `observe -> plan -> act -> verify`
2. [Day 02: Setup môi trường và workflow cơ bản](./Day-02/lession) — cài CLI, scaffold project `taskflow-ai`, dùng `/init`, permission cơ bản
3. [Day 04: Permission modes và an toàn](./Day-04/lession) — chọn đúng mode (`plan`, `default`, `acceptEdits`), workflow plan-first
4. [Day 05: CLAUDE.md chuẩn cho project](./Day-05/lession) — project memory để Claude không quên convention giữa các session
5. [Day 06: Prompt engineering cho coding task](./Day-06/lession) — format `Context -> Goal -> Constraints -> AC -> Verification`
6. [Day 08: Backend CRUD với plan-first workflow](./Day-08/lession) — implement API CRUD có kiểm soát, API contract, review diff
7. [Day 11: Testing với Claude Code](./Day-11/lession) — unit test, integration test, E2E, không để AI quyết định assertion

Sau 7 bài này bạn đã có thể dùng Claude Code để implement feature thật trong repo với quy trình an toàn. Phần còn lại mở rộng để tự động hóa, tối ưu và đưa vào team workflow.

## Cấu trúc khóa học

| Phase | Ngày | Chủ đề | Deliverable chính |
|---|---|---|---|
| Phase 1 — Nền tảng & Agentic Coding | Day 01-04 | Mindset, Setup, Session, Permission | Sandbox `taskflow-ai` + workflow an toàn |
| Phase 2 — Memory & Context Engineering | Day 05-07 | CLAUDE.md, Prompt Engineering, Codebase Discovery | `CLAUDE.md` + `ARCHITECTURE.md` |
| Phase 3 — Build Feature Thực Tế | Day 08-11 | Backend CRUD, Migration, Frontend, Testing | Feature CRUD + test suite |
| Phase 4 — Automation | Day 12-15 | Hooks, Skills, Subagents, MCP | Guardrails + workflow tái sử dụng |
| Phase 5 — Team & Production | Day 16-20 | GitHub, Refactor, Security, Cost, Capstone | PR + capstone feature `task comments` |

## Mức độ ưu tiên (80/20 analysis)

### Nhóm A — Bắt buộc học trước (20% kiến thức tạo 80% giá trị)

| Bài | Chủ đề | Vì sao quan trọng |
|---|---|---|
| Day 01 | Mindset: Claude Code không phải chatbot | Nền tảng tư duy, quyết định mọi workflow sau này |
| Day 02 | Setup môi trường và workflow cơ bản | Không setup thì không làm được gì |
| Day 04 | Permission modes và an toàn | Guardrail quan trọng nhất trước khi cho AI sửa code |
| Day 05 | CLAUDE.md chuẩn cho project | Project memory để Claude nhất quán giữa các session |
| Day 06 | Prompt engineering cho coding task | Kỹ năng dùng hằng ngày, quyết định quality output |
| Day 08 | Backend CRUD với plan-first workflow | Pattern implement feature thực tế đầu tiên |
| Day 11 | Testing với Claude Code | Kiểm soát chất lượng, tránh bẫy "coverage ảo" |

### Nhóm B — Nên học sớm

| Bài | Chủ đề | Vì sao nên học sớm |
|---|---|---|
| Day 03 | Session, context window, resume/continue | Quản lý context hiệu quả, tránh nhiễu khi làm task dài |
| Day 07 | Khám phá codebase lớn | Kỹ năng cần khi làm việc với repo thực tế nhiều module |
| Day 10 | Frontend workflow với React | Quan trọng nếu bạn làm full-stack hoặc frontend |
| Day 16 | GitHub workflow với Claude Code | Áp dụng ngay khi làm việc team: branch, PR, review |
| Day 19 | Performance, token, cost, context optimization | Giúp tiết kiệm token và tối ưu hiệu suất làm việc |

### Nhóm C — Học sau khi đã làm được project cơ bản

| Bài | Chủ đề | Khi nào quay lại |
|---|---|---|
| Day 09 | Database migration và data model | Khi cần thao tác với database thật, migration có rủi ro |
| Day 12 | Hooks trong Claude Code | Khi cần tự động hóa guardrail cho team |
| Day 13 | Skills tái sử dụng | Khi có workflow lặp lại cần đóng gói thành chuẩn |
| Day 14 | Subagents cho workflow chuyên biệt | Khi workflow phức tạp, cần tách context riêng cho từng vai trò |
| Day 15 | MCP servers | Khi cần kết nối external tools: browser, database, GitHub |
| Day 17 | Refactor legacy code an toàn | Khi gặp code cũ cần sửa nhưng sợ break behavior |
| Day 18 | Security review và production guardrails | Khi chuẩn bị đưa code lên production |
| Day 20 | Capstone: build feature end-to-end | Sau khi đã học hết nhóm A, B, C — tổng hợp toàn bộ |

### Nhóm D — Đọc lướt / tra cứu

| Bài | Chủ đề | Ghi chú |
|---|---|---|
| Các file `document.md` | Chi tiết mở rộng, bảng so sánh, lỗi thường gặp | Đọc như tài liệu tham khảo khi cần |
| `exercise.md` phần nâng cao | Bài tập nâng cao mỗi ngày | Làm sau khi đã hoàn thành phần cơ bản + thực tế |
| Day 20 (postmortem, rollback) | Đánh giá và ghi nhớ | Đọc để biết, apply khi cần |

## Cách học đề xuất

1. **Ưu tiên Phase 1 + 2 trước** (Day 01-07): đây là 20% kiến thức tạo 80% giá trị. Học xong bạn đã có workflow an toàn để dùng Claude Code.
2. **Sau đó làm Phase 3** (Day 08-11): implement feature thật với CRUD, database, frontend, test.
3. **Phase 4** (Day 12-15): học khi cần tự động hóa workflow lặp lại.
4. **Phase 5** (Day 16-20): học khi chuẩn bị đưa workflow vào team production thật.

Mỗi ngày học 2 giờ theo format:
- 10 phút: đọc TL;DR và mục tiêu
- 35 phút: học concept chính (đọc `lession.md`)
- 45 phút: hands-on (làm `exercise.md`, tham khảo `document.md`)
- 20 phút: ghi chú trade-off, performance concern
- 10 phút: update learning log

## Lộ trình chi tiết theo từng giai đoạn

### Giai đoạn 1 — Nền tảng và workflow an toàn

**Thời lượng:** ~14 giờ (Day 01-07)

Nên học:
1. Day 01 — Mindset: Claude Code không phải chatbot
2. Day 02 — Setup môi trường và workflow cơ bản
3. Day 03 — Session, context window, resume/continue
4. Day 04 — Permission modes và an toàn
5. Day 05 — CLAUDE.md chuẩn cho project
6. Day 06 — Prompt engineering cho coding task
7. Day 07 — Khám phá codebase lớn

Mục tiêu:
- Hiểu agentic coding khác chatbot và autocomplete thế nào
- Có repo `taskflow-ai` với scaffold backend/frontend
- Biết chọn permission mode đúng cho từng loại task
- Viết được `CLAUDE.md` cho project
- Viết prompt có cấu trúc `Context -> Goal -> Constraints -> AC -> Verification`
- Dùng Claude Code khám phá codebase và tạo `ARCHITECTURE.md`

### Giai đoạn 2 — Build feature thực tế

**Thời lượng:** ~8 giờ (Day 08-11)

Nên học:
1. Day 08 — Backend CRUD với plan-first workflow
2. Day 09 — Database migration và data model
3. Day 10 — Frontend workflow với React
4. Day 11 — Testing với Claude Code

Mục tiêu:
- Implement backend CRUD có API contract, validation, test
- Thiết kế data model và migration an toàn
- Xây dựng UI React kết nối với API thật
- Viết unit test, integration test, E2E test có assertion thật

### Giai đoạn 3 — Automation và team workflow

**Thời lượng:** ~12 giờ (Day 12-16, 19)

Nên học:
1. Day 12 — Hooks trong Claude Code
2. Day 13 — Skills tái sử dụng
3. Day 14 — Subagents cho workflow chuyên biệt
4. Day 15 — MCP servers
5. Day 16 — GitHub workflow với Claude Code
6. Day 19 — Performance, token, cost, context optimization

Mục tiêu:
- Tạo hook chặn command nguy hiểm và tự động format code
- Xây dựng skill `api-reviewer` và `test-writer` tái sử dụng
- Thiết kế subagent cho plan, implement, review, test
- Kết nối MCP Playwright để UI testing tự động
- Tạo PR workflow an toàn với Claude Code

### Giai đoạn 4 — Production readiness và capstone

**Thời lượng:** ~8 giờ (Day 17-18, 20)

Nên học:
1. Day 17 — Refactor legacy code an toàn
2. Day 18 — Security review và production guardrails
3. Day 20 — Capstone: build feature end-to-end

Mục tiêu:
- Refactor legacy code bằng characterization test + Strangler Fig
- Audit secret leakage, prompt injection, dependency risk
- Build feature `task comments` end-to-end với mọi guardrail
- Viết PR description, postmortem, rollback plan

## Mini project — taskflow-ai

**Mô tả:** Ứng dụng quản lý task mini cho team kỹ thuật, xây dựng xuyên suốt khóa học.

**Stack mặc định:**
- Backend: Node.js + TypeScript + Fastify/NestJS
- Database: PostgreSQL + Redis
- Frontend: React + Vite
- Test: Vitest/Jest + Playwright
- DevOps: Docker Compose

**Kiến thức áp dụng:**
- Agentic coding workflow (`observe -> plan -> act -> verify`)
- Plan-first CRUD với API contract
- Database migration an toàn
- Component boundary React + state management tối giản
- Test pyramid: unit, integration, E2E
- Hook guardrails, skill tái sử dụng, subagent chuyên biệt
- MCP browser automation
- GitHub PR workflow + code review
- Security audit và context/cost optimization

**Tiêu chí hoàn thành:**
- Có prompt đã dùng và output quan trọng cho mỗi ngày
- Có diff hoặc artifact rõ ràng trong repo `taskflow-ai`
- Có command verify: typecheck, test, lint
- Có ghi chú rủi ro: security, maintainability, context, permission
- Feature `task comments` chạy end-to-end: database -> API -> UI -> test -> PR

## Checklist học nhanh

- [ ] Tôi đã hiểu Claude Code là agentic terminal tool, không phải chatbot
- [ ] Tôi đã học xong toàn bộ nhóm A (Day 01, 02, 04, 05, 06, 08, 11)
- [ ] Tôi đã scaffold được `taskflow-ai` và implement CRUD đầu tiên
- [ ] Tôi đã viết `CLAUDE.md` và biết review diff trước khi accept
- [ ] Tôi đã biết chọn permission mode đúng cho từng loại task
- [ ] Tôi đã học tiếp các bài nhóm B (Day 03, 07, 10, 16, 19)
- [ ] Tôi biết phần nào thuộc nhóm C/D để quay lại sau

## Flashcard / câu hỏi ôn tập gợi ý

1. Claude Code khác chatbot ở điểm nào?
   - **Đáp án:** Là agentic terminal tool, có thể đọc/sửa file, chạy command, làm việc trong repo thật.
   - **Liên quan:** Day 01

2. Vòng lặp agentic coding cơ bản là gì?
   - **Đáp án:** `observe -> plan -> act -> verify`
   - **Liên quan:** Day 01

3. Permission mode nào nên dùng khi bắt đầu một task có rủi ro?
   - **Đáp án:** `plan` — chỉ cho phép đọc file và chạy command read-only.
   - **Liên quan:** Day 04

4. `CLAUDE.md` dùng để làm gì?
   - **Đáp án:** Project memory / onboarding document cho AI, chứa stack, commands, conventions, security rules.
   - **Liên quan:** Day 05

5. Cấu trúc prompt coding task tốt gồm những phần nào?
   - **Đáp án:** Context -> Goal -> Constraints -> Acceptance Criteria -> Verification
   - **Liên quan:** Day 06

6. Khi nào nên dùng session dài trong Claude Code?
   - **Đáp án:** Task cùng mục tiêu, cần giữ quyết định đã thống nhất, đang debug nhiều bước.
   - **Liên quan:** Day 03

7. Hook `PreToolUse` dùng để làm gì?
   - **Đáp án:** Chặn command nguy hiểm trước khi Bash tool chạy, ví dụ `rm -rf`.
   - **Liên quan:** Day 12

8. Skill khác gì với prompt dài?
   - **Đáp án:** Skill là module tái sử dụng có frontmatter, instruction, tool giới hạn, có thể gọi bằng `/skill-name`.
   - **Liên quan:** Day 13

9. Subagent giải quyết vấn đề gì?
   - **Đáp án:** Context window riêng cho từng vai trò (planner, reviewer, tester), giảm nhiễu và bias.
   - **Liên quan:** Day 14

10. Khi nào không nên dùng Claude Code?
    - **Đáp án:** Khi có secret thật trong context, task auth/payment/migration chưa có reviewer, chưa biết acceptance criteria, không có thời gian đọc diff.
    - **Liên quan:** Day 01, Day 04

11. `strangler fig pattern` trong refactor là gì?
    - **Đáp án:** Tạo facade giữ API cũ, chuyển dần từng case sang implementation mới, không rewrite một lần.
    - **Liên quan:** Day 17

12. Làm sao để kiểm tra context usage trong Claude Code?
    - **Đáp án:** Dùng `/usage` hoặc `/context` để xem token usage và phần nào đang chiếm context.
    - **Liên quan:** Day 19

## Tài nguyên

- [README tổng quan khóa học](./README.md)
- [Claude Code Quickstart](https://code.claude.com/docs/en/quickstart)
- [Claude Code Sessions](https://code.claude.com/docs/en/sessions)
- [Claude Code Permissions](https://code.claude.com/docs/en/permissions)
- [Claude Code Best Practices](https://code.claude.com/docs/en/best-practices)
