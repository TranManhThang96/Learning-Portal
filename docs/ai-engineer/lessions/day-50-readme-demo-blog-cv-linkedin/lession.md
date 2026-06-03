# Day 50: README, Demo, Blog, CV/LinkedIn

## Mục Tiêu

Sau ngày cuối, bạn cần biến capstone thành portfolio package có thể gửi cho recruiter, hiring manager hoặc interviewer:

- README chuyên nghiệp: problem, architecture, setup, API, eval, security, cost và limitations.
- Demo script 3-5 phút thể hiện ingestion, query, citation, trace và evaluation.
- Blog outline giải thích engineering decisions và trade-offs.
- CV bullet points bằng English, tập trung impact và production engineering.
- LinkedIn post bằng tiếng Việt hoặc English.
- Portfolio checklist trước khi public GitHub repo.
- Trả lời được: project này có thể dùng production không, và cần điều kiện gì.

## TL;DR

Day 50 biến capstone từ "project chạy được" thành "portfolio artifact thuyết phục". Reviewer không chỉ cần thấy chatbot trả lời, mà cần thấy bạn hiểu production RAG: ingestion, hybrid retrieval, reranking, citation validation, permission-aware retrieval, guardrails, observability, eval gate và cost control. README, demo, blog, CV và LinkedIn phải kể cùng một câu chuyện: bạn có thể đưa LLM/RAG app vào production boundary.

## 1. Portfolio Package Là Gì?

Portfolio package là bộ bằng chứng để reviewer đánh giá nhanh:

```text
GitHub repo
  -> README
  -> architecture diagram
  -> setup instructions
  -> sample data
  -> demo script/video
  -> eval report
  -> security/cost notes
  -> known limitations
  -> CV/LinkedIn positioning
```

Với Senior SE chuyển sang AI Engineer, portfolio tốt cần chứng minh 3 nhóm năng lực:

| Nhóm năng lực | Bằng chứng trong portfolio |
|---|---|
| AI/RAG engineering | chunking, embedding, hybrid search, rerank, citation, eval |
| Production engineering | API contract, Docker Compose, config, logging, trace, CI |
| Product judgment | scope rõ, limitations thật, cost/security trade-off |

Không nên trình bày project như "chatbot với tài liệu". Nên trình bày như "Vietnamese Enterprise Knowledge Assistant có citation, permission, evaluation và monitoring".

## 2. README Chuyên Nghiệp

README là entry point của repo. Nó phải giúp reviewer trả lời nhanh:

- Project giải quyết vấn đề gì?
- Chạy local như thế nào?
- Architecture có gì đáng tin?
- RAG pipeline hoạt động ra sao?
- Eval có metric gì?
- Security/cost được nghĩ đến chưa?
- Limitations là gì?

README outline:

| Section | Nội dung |
|---|---|
| Problem | Tài liệu doanh nghiệp phân tán, keyword search yếu, raw LLM dễ hallucinate/leak |
| Features | Ingestion, chunking, hybrid search, rerank, citation, ACL, trace, eval |
| Architecture | Text diagram tách indexing, query và eval path |
| Tech stack | API, UI, vector DB, BM25, embedding, reranker, LLM, observability |
| RAG pipeline | Validate -> ACL -> retrieve -> rerank -> generate -> validate citation |
| API examples | `/health`, `/ready`, `/documents/ingest`, `/query`, `/traces/{id}` |
| Run locally | `.env.example`, Docker Compose, ingest sample docs, run eval |
| Evaluation result | Recall@K, MRR, citation correctness, faithfulness, no-answer, latency/cost |
| Security | ACL before retrieval/context, prompt injection, PII-safe logs, citation validation |
| Cost | Token budget, context cap, reranker timeout, eval separated from realtime |
| Known limitations | Demo auth, sample corpus, eval size, UI scope, provider dependency |
| Future improvements | SSO, async ingestion, dashboard, canary, document lifecycle |

Opening gợi ý:

````markdown
# Vietnamese Enterprise Knowledge Assistant

Production-style RAG assistant for Vietnamese enterprise documents with citation,
permission-aware retrieval, evaluation and LLM observability.
````

## 3. README Template

````markdown
# Vietnamese Enterprise Knowledge Assistant

Production-style RAG assistant for Vietnamese enterprise documents with citation,
permission-aware retrieval, evaluation and LLM observability.

## Problem

Enterprise documents are scattered across PDF, Markdown and internal policy files.
Keyword search is weak for Vietnamese queries, while raw LLM answers can hallucinate
or expose data users should not see.

## Features

- Document ingestion for PDF/Markdown/Text.
- Structure-aware chunking with metadata.
- Hybrid retrieval using BM25 + vector search.
- RRF merge and reranking.
- Permission-aware retrieval by tenant and roles.
- Grounded answer generation with source citations.
- Citation validation and PII-safe logs.
- Trace logging for latency, token usage and estimated cost.
- Golden-set evaluation with release thresholds.

## Architecture

```text
Frontend
  -> Backend API
      -> Auth/Tenant Context
      -> Ingestion Pipeline
      -> RAG Orchestrator
          -> Query Normalizer
          -> BM25 Retriever
          -> Vector Retriever
          -> RRF Merger
          -> Reranker
          -> Context Builder
          -> LLM Gateway
          -> Citation Validator
      -> Trace Store
      -> Eval Runner
```

## Run Locally

```bash
cp .env.example .env
docker compose up --build
python scripts/ingest.py --input data/raw
python scripts/evaluate.py --golden-set data/eval/golden_set.jsonl
```

## Query Example

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Nhân viên được nghỉ phép năm bao nhiêu ngày?",
    "tenant_id": "demo",
    "user_id": "reviewer",
    "roles": ["employee"]
  }'
```

## Evaluation

| Metric | Result | Threshold |
|---|---:|---:|
| Recall@5 | 0.86 | 0.80 |
| MRR@10 | 0.74 | 0.70 |
| Citation correctness | 0.96 | 0.95 |
| Format pass rate | 1.00 | 0.98 |
| No-answer accuracy | 0.92 | 0.90 |

## Security And Guardrails

- Tenant/role filters are applied before context building.
- Retrieved context is treated as data, not instructions.
- Response schema and citations are validated.
- PII is redacted before logs/traces.
- Prompt injection and no-answer cases are included in evaluation.

## Cost Notes

- Context is capped by token budget.
- Reranker top-k is configurable.
- Eval runs are separated from realtime traffic.
- Model routing can use cheaper models for low-risk requests.

## Limitations

- Demo authentication uses roles in the request.
- Sample corpus is small.
- Evaluation set needs more domain-labeled examples.
- UI is intentionally minimal.
````

## 4. Demo Video Script 3-5 Phút

```text
0:00 - 0:20 Problem
"Đây là Vietnamese Enterprise Knowledge Assistant. Project giải quyết bài toán hỏi đáp tài liệu nội bộ tiếng Việt với citation, permission-aware retrieval, evaluation và observability."

0:20 - 0:50 Architecture
"System tách indexing path, query path và eval path. Indexing parse/chunk/embed/index documents. Query path dùng BM25 + vector search, RRF merge, rerank, context builder, LLM gateway và citation validator."

0:50 - 1:30 Run local
"Repo chạy bằng Docker Compose. API, UI và vector DB được start local. `.env.example` cấu hình model provider, embedding, reranker, top-k và token budget."

1:30 - 2:10 Ingestion
"Tôi ingest sample HR/IT policy documents. Mỗi chunk có metadata: tenant_id, doc_id, page, section, acl_roles, document_version và index_version."

2:10 - 3:00 Query with citation
"Tôi hỏi một câu tiếng Việt về chính sách nghỉ phép. System trả answer kèm citation [S1], và citation map về doc/page/section thật."

3:00 - 3:40 Permission/no-answer
"Tôi hỏi câu ngoài tài liệu hoặc câu không có quyền. System không hallucinate, trả response không đủ thông tin hoặc refuse theo policy."

3:40 - 4:20 Trace
"Mỗi request có trace_id. Trace cho thấy retrieve latency, rerank latency, generate latency, token usage, estimated cost, prompt/model/index version."

4:20 - 5:00 Evaluation
"Cuối cùng tôi mở golden eval report. Report gồm Recall@K, MRR, citation correctness, no-answer accuracy, format pass rate và release decision."
```

Demo checklist:

- Repo start được bằng một lệnh.
- Có sample docs sẵn.
- Có 3 query mẫu: normal, no-answer, ACL.
- Citation visible.
- Trace ID và latency per stage visible.
- Có eval report.
- Không lộ API key/secret.
- Không dùng document có data nhạy cảm thật.

## 5. Blog Outline

Title:

```text
Building a Production-Style Vietnamese Enterprise RAG Assistant
```

Outline:

1. Problem: enterprise knowledge search in Vietnamese.
2. Why raw LLM is not enough.
3. Architecture: indexing, query, eval paths.
4. Chunking and metadata design.
5. Hybrid retrieval: BM25 + vector search.
6. Reranking and context building.
7. Citation validation and no-answer policy.
8. Permission-aware retrieval.
9. Guardrails: prompt injection, PII-safe logs, output schema.
10. Evaluation with golden set and CI thresholds.
11. Observability: latency, cost, trace and feedback.
12. Trade-offs and limitations.
13. What I would improve next.

Key message:

> The hard part of production RAG is not calling an LLM. It is controlling context, permissions, evaluation, observability and failure modes.

## 6. CV Bullet Points

Use English, action-first, evidence-driven:

- Built a production-style Vietnamese Enterprise RAG Assistant using FastAPI, hybrid search, reranking, source citation and LLM observability.
- Designed a permission-aware retrieval pipeline with tenant/role filtering, citation validation and PII-safe trace logging.
- Implemented a golden-set evaluation workflow measuring Recall@K, MRR, citation correctness, no-answer accuracy and format pass rate.
- Added guardrails for prompt injection defense, structured output validation, no-answer handling and safe logging.
- Created a portfolio-ready demo with API contract, Docker Compose setup, evaluation report, monitoring summary and documented trade-offs.

Avoid weak bullets:

- "Made a chatbot."
- "Used LangChain."
- "Worked with AI."
- "Implemented RAG."

They do not show production judgment.

## 7. LinkedIn Post Mẫu

Tiếng Việt:

```text
Tôi vừa hoàn thành capstone project: Vietnamese Enterprise Knowledge Assistant.

Đây không chỉ là chatbot hỏi đáp tài liệu. Mục tiêu của project là xây một RAG system theo hướng production-style cho tài liệu doanh nghiệp tiếng Việt:

- Ingestion pipeline cho PDF/Markdown/Text
- Hybrid retrieval: BM25 + vector search
- Reranking và context building
- Citation theo source/page/section/chunk
- Permission-aware retrieval theo tenant/role
- Guardrails cho prompt injection, output validation và PII-safe logging
- Golden-set evaluation với Recall@K, MRR, citation correctness và no-answer accuracy
- Trace latency/token/cost cho mỗi request

Điều tôi học được: phần khó của production RAG không phải là gọi LLM, mà là kiểm soát context, quyền truy cập, citation, evaluation, observability và failure modes.

Repo/demo: thêm URL repo hoặc video demo khi public.
```

English:

```text
I just completed a capstone project: Vietnamese Enterprise Knowledge Assistant.

It is a production-style RAG assistant for Vietnamese enterprise documents, focused on:

- PDF/Markdown/Text ingestion
- Hybrid retrieval with BM25 + vector search
- Reranking and context building
- Source citations by document/page/section/chunk
- Permission-aware retrieval by tenant and role
- Guardrails for prompt injection, structured output validation and PII-safe logging
- Golden-set evaluation with Recall@K, MRR, citation correctness and no-answer accuracy
- Per-request tracing for latency, token usage and estimated cost

The main lesson: production RAG is less about calling an LLM and more about controlling context, permissions, citations, evaluation, observability and failure modes.

Repo/demo: add the repository or demo video URL when publishing.
```

## 8. Trade-Offs Khi Public Portfolio

| Quyết định | Lợi ích | Trade-off |
|---|---|---|
| Public full code | Dễ review | Phải scrub secrets/data |
| Public sample data | Demo dễ | Cần synthetic/non-sensitive data |
| Include eval report | Tăng credibility | Phải giải thích limitations |
| Include cost numbers | Thể hiện production mindset | Numbers thay đổi theo provider |
| Show architecture diagram | Dễ hiểu | Phải giữ sync với code |
| Mention limitations | Tạo trust | Không nên tự làm yếu project bằng wording quá tiêu cực |

Best solution:

- Public code + synthetic data + `.env.example`.
- Không public raw company data.
- README ghi rõ limitations và next steps.
- Demo video dùng sample docs.
- CV bullets tập trung vào decisions và metrics, không phóng đại.

## 9. Dùng Được Trong Production Không?

Capstone này có thể là nền tảng production-style, nhưng để dùng production thật cần thêm điều kiện.

Điều kiện production:

- Auth/SSO thật, không dùng demo roles trong request.
- Tenant/role/ACL enforce ở backend và storage layer.
- Secret management đúng chuẩn.
- Corpus/data đã qua privacy review.
- Evaluation set đủ lớn và representative.
- Monitoring/alerting realtime.
- Incident response và rollback plan.
- Load test/capacity planning.
- Security review cho prompt injection, data leakage, file upload.
- Backup/migration cho vector DB và metadata store.

Trong portfolio, nên nói:

> This is a production-style capstone designed to demonstrate architecture, evaluation, guardrails and observability. It is not a drop-in enterprise product without real auth, security review, larger domain evaluation and operational hardening.

## Checklist Cuối Khóa

- [ ] README final.
- [ ] `.env.example` không chứa secret.
- [ ] Docker/local setup chạy được.
- [ ] Sample docs không nhạy cảm.
- [ ] Demo script 3-5 phút.
- [ ] Evaluation report.
- [ ] Monitoring summary.
- [ ] Blog outline.
- [ ] CV bullet points.
- [ ] LinkedIn post.
- [ ] Known limitations rõ ràng.
- [ ] Repo public không chứa API key, PII hoặc file nội bộ thật.
