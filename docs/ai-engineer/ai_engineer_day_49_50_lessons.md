# 2 Bai Hoc Cuoi Cho AI Engineer

Nguon: `lo_trinh_50_ngay_senior_se_to_ai_engineer.md`, Phase 7 - Capstone & Portfolio.

Doi tuong: Senior Software Engineer muon chuyen sang AI Engineer / GenAI Engineer / Backend Engineer with AI focus.

Khung hoc moi ngay: 2 gio.

## Muc Luc

| Ngay | Chu de | Output chinh |
|---:|---|---|
| Day 49 | UI, Monitoring, Evaluation Report | Chat UI + citations + feedback + monitoring summary + evaluation report |
| Day 50 | README, Demo, Blog, CV/LinkedIn | Portfolio package cho Vietnamese Enterprise Knowledge Assistant |

## File Chi Tiet

| Ngay | File |
|---:|---|
| Day 49 | [UI, Monitoring, Evaluation Report](./bai-hoc-day-49-50/day-49-ui-monitoring-evaluation-report.md) |
| Day 50 | [README, Demo, Blog, CV/LinkedIn](./bai-hoc-day-49-50/day-50-readme-demo-blog-cv-linkedin.md) |

## Tong Quan Learning Path

Day 49-50 ket thuc Phase 7: Capstone & Portfolio. Neu Day 48 da dong scope va hoan thien backend/API, hai ngay cuoi bien project thanh artifact co the review, demo va dua vao CV/LinkedIn.

Day 49 tap trung vao trai nghiem review va bang chung chat luong: UI chat can hien answer, citation, trace id, latency, token/cost va feedback. Golden evaluation phai tao report co metrics, top failures, root cause va release decision.

Day 50 tap trung vao packaging: README final, demo script, blog outline, CV bullets, LinkedIn post va checklist truoc khi public repo. Muc tieu khong phai noi "toi build chatbot", ma chung minh ban co production judgment cho LLM/RAG system.

## Artifact Nen Co Sau Day 49-50

| Artifact | Den tu ngay | Gia tri production/portfolio |
|---|---:|---|
| Chat UI | Day 49 | Reviewer thao tac duoc voi assistant |
| Citation panel | Day 49 | Chung minh answer grounded trong source |
| Feedback thumbs up/down | Day 49 | Noi user signal voi trace |
| Monitoring summary | Day 49 | Do latency, cost, retrieval va citation health |
| Evaluation report | Day 49 | Co release evidence, threshold va top failures |
| README final | Day 50 | Reviewer hieu problem, architecture, setup va trade-off |
| Demo script | Day 50 | Demo 3-5 phut co normal, no-answer va ACL case |
| Blog outline | Day 50 | Giai thich engineering decisions va lessons learned |
| CV bullets | Day 50 | Position project theo role AI/GenAI Engineer |
| LinkedIn post | Day 50 | Public portfolio ro khac biet voi chatbot demo |

## Production Gate

Truoc khi coi capstone san sang public, can co it nhat:

- UI query duoc backend va hien answer + citations + trace id.
- Citation map ve `doc_id`, `chunk_id`, page/section that.
- Feedback gan voi `trace_id`.
- Trace log co latency theo stage, token usage, cost estimate va version.
- Evaluation report co Recall@K, MRR, citation correctness, faithfulness, format pass rate va no-answer accuracy.
- Metrics chia theo tags quan trong: `acl`, `no-answer`, `prompt-injection`, `multi-hop`, `vietnamese`.
- README co quickstart, architecture, API examples, eval result, security/cost considerations va limitations.
- Demo script co 3 case: normal query, no-answer, ACL/permission.
- Repo khong co secret, PII, broken links hoac instructions khong chay duoc.

## Final Portfolio Story

Mot cau chuyen tot cho capstone:

```text
Vietnamese Enterprise Knowledge Assistant la production-style RAG assistant
cho tai lieu doanh nghiep tieng Viet. System co ingestion, metadata-rich
chunking, hybrid search, reranking, citation validation, permission-aware
retrieval, observability, evaluation va Docker Compose local deployment.
```

Trong interview, dung project nay de noi ve:

- Vi sao RAG khong chi la prompt + vector search.
- Cach tach indexing path, query path va eval path.
- Cach metadata quyet dinh citation va permission safety.
- Vi sao hybrid search + rerank can duoc do bang eval, khong chon cam tinh.
- Cach trace giup debug fail do retriever, reranker, prompt hay model.
- Cach token budget va monitoring giup LLM app van hanh duoc.

## Learning Cadence

| Thoi luong | Viec lam |
|---:|---|
| 10 phut | Doc TL;DR va muc tieu |
| 35 phut | Hoc concept chinh |
| 45 phut | Hands-on/code/design |
| 20 phut | Ghi chu trade-off, performance, production concern |
| 10 phut | Update learning log |

