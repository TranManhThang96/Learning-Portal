# Claude Code Practical Course

Khóa học thực hành Claude Code cho developer mid-level đến senior muốn dùng agentic coding trong công việc thật nhưng vẫn kiểm soát chất lượng, security, maintainability và chi phí context.

## Mục tiêu khóa học

- Hiểu Claude Code như một agentic terminal tool, không xem nó như chatbot trả lời rời rạc.
- Biết thiết kế workflow `observe -> plan -> act -> verify` cho task coding thật.
- Dùng Claude Code để đọc codebase, lập kế hoạch, sửa code, viết test, review diff và hỗ trợ Git workflow.
- Quản lý session, context window, permission modes, project memory, hooks, skills, subagents, MCP và production guardrails.
- Xây dựng dần project xuyên suốt `taskflow-ai` theo hướng có thể đem vào team thật.

## Ai nên học

- Developer đã có kinh nghiệm với ít nhất một stack backend hoặc frontend.
- Tech lead, senior engineer, reviewer muốn tăng tốc delivery mà không đánh đổi ownership.
- Team đang thử đưa AI coding assistant vào workflow nhưng cần quy tắc vận hành rõ ràng.

Khóa học không phù hợp nếu bạn chỉ muốn copy prompt để sinh code nhanh mà không review, test, rollback hoặc kiểm soát quyền chạy lệnh.

## Prerequisites

- Biết Git cơ bản: branch, commit, diff, pull request.
- Biết chạy terminal và đọc log lỗi.
- Có kinh nghiệm tối thiểu với một stack như Node.js, Python, Go, PHP, Java hoặc React.
- Cài sẵn editor, Git, package manager của stack bạn chọn.
- Có quyền dùng Claude Code trong môi trường học tập hoặc sandbox.

## Cách học mỗi ngày

Mỗi ngày được thiết kế khoảng 2 tiếng:

1. Đọc `lession.md` để nắm bối cảnh, nguyên tắc và workflow.
2. Mở `document.md` khi cần tra nhanh sơ đồ, bảng so sánh, lỗi thường gặp và link tài liệu.
3. Làm `exercise.md` theo thứ tự cơ bản, thực tế, nâng cao, review & reflection.
4. Luôn chạy Claude Code trong repo học tập hoặc sandbox trước khi áp dụng vào repo công ty.
5. Sau mỗi bài, ghi lại prompt tốt, prompt tệ, diff đã accept và lỗi cần tránh.

## Cấu trúc folder

```txt
claude-code-course/
  README.md
  Day-01/
    lession.md
    document.md
    exercise.md
  Day-02/
    lession.md
    document.md
    exercise.md
  Day-03/
    lession.md
    document.md
    exercise.md
  Day-04/
    lession.md
    document.md
    exercise.md
  Day-05/
    lession.md
    document.md
    exercise.md
  Day-06/
    lession.md
    document.md
    exercise.md
  Day-07/
    lession.md
    document.md
    exercise.md
  Day-08/
    lession.md
    document.md
    exercise.md
  Day-09/
    lession.md
    document.md
    exercise.md
  Day-10/
    lession.md
    document.md
    exercise.md
  Day-11/
    lession.md
    document.md
    exercise.md
  Day-12/
    lession.md
    document.md
    exercise.md
  Day-13/
    lession.md
    document.md
    exercise.md
  Day-14/
    lession.md
    document.md
    exercise.md
  Day-15/
    lession.md
    document.md
    exercise.md
  Day-16/
    lession.md
    document.md
    exercise.md
  Day-17/
    lession.md
    document.md
    exercise.md
  Day-18/
    lession.md
    document.md
    exercise.md
  Day-19/
    lession.md
    document.md
    exercise.md
  Day-20/
    lession.md
    document.md
    exercise.md
```

Lưu ý: tên file `lession.md` được giữ đúng theo yêu cầu của plan.

## Project xuyên suốt

**Tên project:** `taskflow-ai`

**Mô tả:** ứng dụng quản lý task mini cho team kỹ thuật.

Stack mặc định:

- Backend: Node.js + TypeScript + Fastify hoặc NestJS.
- Database: PostgreSQL.
- Cache: Redis.
- Frontend: React + Vite.
- Test: Vitest hoặc Jest.
- E2E: Playwright.
- DevOps cơ bản: Docker Compose.
- GitHub workflow: branch, pull request, code review.

Nếu dùng Go, Python hoặc PHP, giữ nguyên mục tiêu học: Claude Code phải đọc được cấu trúc project, biết command chuẩn, có acceptance criteria rõ ràng, và mọi thay đổi đều được kiểm tra bằng test hoặc review diff.

## Lộ trình 20 ngày

### Phase 1 - Nền tảng Claude Code và agentic coding

- [Day 01 - Mindset: Claude Code không phải chatbot](./Day-01/lession.md)
- [Day 02 - Setup môi trường và workflow cơ bản](./Day-02/lession.md)
- [Day 03 - Session, context window, resume/continue](./Day-03/lession.md)
- [Day 04 - Permission modes và an toàn khi cho AI sửa code](./Day-04/lession.md)

### Phase 2 - Memory và context engineering

- [Day 05 - CLAUDE.md chuẩn cho project](./Day-05/lession.md)
- [Day 06 - Prompt engineering cho coding task](./Day-06/lession.md)
- [Day 07 - Khám phá codebase lớn](./Day-07/lession.md)

### Phase 3 - Build feature thực tế với Claude Code

- [Day 08 - Backend CRUD với plan-first workflow](./Day-08/lession.md)
- [Day 09 - Database migration và data model](./Day-09/lession.md)
- [Day 10 - Frontend workflow với React](./Day-10/lession.md)
- [Day 11 - Testing với Claude Code](./Day-11/lession.md)

### Phase 4 - Automation: hooks, skills, subagents, MCP

- [Day 12 - Hooks trong Claude Code](./Day-12/lession.md)
- [Day 13 - Skills tái sử dụng](./Day-13/lession.md)
- [Day 14 - Subagents cho workflow chuyên biệt](./Day-14/lession.md)
- [Day 15 - MCP servers](./Day-15/lession.md)

### Phase 5 - Team workflow và production readiness

- [Day 16 - GitHub workflow với Claude Code](./Day-16/lession.md)
- [Day 17 - Refactor legacy code an toàn](./Day-17/lession.md)
- [Day 18 - Security review và production guardrails](./Day-18/lession.md)
- [Day 19 - Performance, token, cost, context optimization](./Day-19/lession.md)
- [Day 20 - Capstone: build feature end-to-end](./Day-20/lession.md)

## Cách đánh giá hoàn thành

Bạn hoàn thành một ngày học khi có đủ các bằng chứng sau:

- Có prompt đã dùng, output quan trọng và quyết định accept/reject.
- Có diff hoặc artifact rõ ràng trong `taskflow-ai`.
- Có command kiểm tra đã chạy, ví dụ typecheck, test, lint hoặc `git diff`.
- Có ghi chú rủi ro: security, maintainability, context, permission.
- Có reflection ngắn: Claude Code giúp gì, sai gì, lần sau cần guardrail gì.

## Quy tắc an toàn khi dùng Claude Code

- Không đưa secret, production credential, customer data hoặc nội dung nhạy cảm vào prompt.
- Không dùng `bypassPermissions` ngoài sandbox cô lập.
- Không auto-approve lệnh destructives như xóa file hàng loạt, reset Git, drop database hoặc migration phá dữ liệu.
- Luôn yêu cầu plan trước với task có blast radius lớn.
- Review `git diff` trước khi accept hoặc commit.
- Tách task lớn thành phần nhỏ để giảm context noise và dễ rollback.
- Dùng `/clear` cho task không liên quan và `/compact <instructions>` khi cần giữ summary có trọng tâm.
- Với tính năng Claude Code có thể thay đổi, kiểm tra official docs trước khi đưa vào workflow team.

## Tài liệu nền

- Claude Code Quickstart: <https://code.claude.com/docs/en/quickstart>
- Claude Code Sessions: <https://code.claude.com/docs/en/sessions>
- Claude Code Permissions: <https://code.claude.com/docs/en/permissions>
- Claude Code Best Practices: <https://code.claude.com/docs/en/best-practices>
