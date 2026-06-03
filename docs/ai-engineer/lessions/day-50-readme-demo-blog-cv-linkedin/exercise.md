# Day 50 Exercise: Đóng Gói Portfolio Capstone

## Mục Tiêu

Bạn sẽ hoàn thiện các artifact cuối cùng:

- `README.md`.
- Demo script.
- Blog outline.
- CV bullets.
- LinkedIn post.
- Public repo checklist.

## Bài Tập 1: Viết README Final

README bắt buộc có:

- Project title.
- Problem statement.
- Features.
- Architecture diagram.
- Tech stack.
- RAG pipeline.
- API examples.
- How to run locally.
- Evaluation result.
- Security considerations.
- Cost considerations.
- Known limitations.
- Future improvements.

Acceptance criteria:

- Reviewer hiểu project trong 2 phút.
- Có lệnh chạy local.
- Có sample query.
- Có link hoặc section evaluation report.
- Không claim quá mức.

## Bài Tập 2: Viết Demo Script

Tạo `docs/demo_script.md` với timeline:

- 0:00 Problem.
- 0:20 Architecture.
- 0:50 Run local.
- 1:30 Ingestion.
- 2:10 Query with citation.
- 3:00 Permission/no-answer.
- 3:40 Trace.
- 4:20 Evaluation.

Chuẩn bị 3 query demo:

1. Normal answer with citation.
2. No-answer/out-of-scope.
3. ACL hoặc prompt injection refusal.

## Bài Tập 3: Viết Blog Outline

Tạo `docs/blog_outline.md` theo structure:

```markdown
# Building a Production-Style Vietnamese Enterprise RAG Assistant

## Why I Built This
## System Architecture
## Ingestion And Chunking
## Hybrid Retrieval And Reranking
## Citation Validation
## Permission-Aware Retrieval
## Guardrails
## Evaluation
## Observability
## Trade-Offs
## What I Would Improve Next
```

Mỗi section viết 3-5 bullets.

## Bài Tập 4: Chuẩn Bị CV Bullets

Viết 3-5 bullets bằng English.

Template:

```text
Built a Vietnamese enterprise RAG assistant using hybrid retrieval and citation validation to demonstrate grounded document Q&A.
Designed a permission-aware retrieval pipeline with tenant filters, role checks and PII-safe trace logging.
Implemented evaluation and observability measuring Recall@K, MRR, citation correctness, latency and cost per request.
```

Ví dụ:

```text
Built a production-style Vietnamese Enterprise RAG Assistant using hybrid search, reranking, citation validation and LLM observability.
Designed a permission-aware retrieval pipeline with tenant/role filtering, PII-safe logs and structured trace metadata.
Implemented a golden-set evaluation workflow measuring Recall@K, MRR, citation correctness, no-answer accuracy and format pass rate.
```

## Bài Tập 5: Viết LinkedIn Post

Viết một bản tiếng Việt hoặc English, dài 120-220 từ.

Bắt buộc nêu:

- Project là gì.
- Tính năng production-style.
- Một lesson learned thật.
- Link repo/demo placeholder.

Không dùng wording quá phóng đại như "enterprise-ready" nếu chưa có auth/security review thật.

## Bài Tập 6: Public Repo Audit

Chạy audit:

```bash
git status --short
rg -n "api[_-]?key|secret|token|password|BEGIN PRIVATE KEY|sk-" .
find . -name ".env" -o -name "*.pem" -o -name "*.key"
```

Kiểm tra thủ công:

- README không chứa secret.
- Sample data không chứa PII.
- Demo screenshots/logs đã redact.
- `.env.example` chỉ có placeholder.
- `evaluation_report.md` ghi limitations.

## Bài Tập 7: Final Portfolio Review

Tự trả lời 6 câu:

1. Reviewer chạy project bằng lệnh nào?
2. Câu demo chính là gì?
3. Citation được validate thế nào?
4. Eval metric nào quan trọng nhất?
5. Risk production lớn nhất là gì?
6. Nếu có thêm 2 tuần, bạn cải thiện gì?

## Checklist Nộp Bài

- [ ] README final.
- [ ] Demo script.
- [ ] Blog outline.
- [ ] CV bullets.
- [ ] LinkedIn post.
- [ ] Public repo safety audit.
- [ ] Evaluation report linked from README.
- [ ] Known limitations rõ và trung thực.
