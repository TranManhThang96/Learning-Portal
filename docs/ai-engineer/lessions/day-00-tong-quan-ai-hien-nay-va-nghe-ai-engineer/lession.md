# Day 00: Tổng Quan AI Hiện Nay Và Nghề AI Engineer

## Mục Tiêu

Sau bài mở đầu này, bạn cần trả lời được 7 câu hỏi nền tảng:

1. AI, Machine Learning, Deep Learning, Generative AI, LLM, RAG và Agent khác nhau thế nào?
2. Vì sao AI bùng nổ trong giai đoạn 2023-2026, nhưng nhiều dự án vẫn mắc kẹt ở pilot?
3. AI Engineer khác gì Data Scientist, ML Engineer, MLOps Engineer và Backend Engineer tích hợp AI?
4. Doanh nghiệp đang dùng AI vào những bài toán thực tế nào?
5. Cơ hội việc làm AI hiện nay nằm ở đâu, và nên đọc tín hiệu thị trường như thế nào?
6. Người mới có nền tảng IT cần học những năng lực nào trước, năng lực nào học sau?
7. Lộ trình 50 ngày này đưa bạn từ Senior SE sang GenAI/RAG/LLM Production Engineer bằng cách nào?

## Cách Học Trong 2 Giờ

| Thời lượng | Việc cần làm | Output |
|---:|---|---|
| 15 phút | Đọc TL;DR và bản đồ thuật ngữ | Không còn nhầm AI/ML/DL/LLM/RAG/Agent |
| 25 phút | Đọc phần thị trường và vai trò nghề nghiệp | Chọn được target role phù hợp |
| 25 phút | Đọc ứng dụng thực tế và trade-off | Biết khi nào AI đáng làm, khi nào chưa |
| 35 phút | Làm bài thực hành ở mục 11 | Có bản đồ năng lực cá nhân và hướng portfolio |
| 20 phút | Làm quiz và checklist cuối bài | Ghi lại câu hỏi cần học sâu ở Day 1-5 |

## TL;DR

AI hiện nay không còn chỉ là training model trong notebook. Phần lớn giá trị thực tế nằm ở việc đưa model, LLM, RAG, agent workflow và evaluation vào sản phẩm có kiểm soát:

```text
AI product = data + model/prompt/retriever + application logic + evaluation + security + observability + cost control
```

Với Senior Software Engineer, lợi thế lớn nhất không phải là biết nhiều paper hơn mọi người. Lợi thế là biết biến AI thành system chạy được: API contract, data pipeline, auth, logging, testing, deployment, rollback, monitoring và cost budget.

Điểm cần nhớ:

- AI là umbrella term. ML, Deep Learning, GenAI, LLM, RAG và Agent là các nhánh/cách triển khai khác nhau.
- Không phải bài toán nào cũng cần LLM. Rule, SQL, search truyền thống hoặc classical ML thường tốt hơn nếu bài toán đơn giản, cần latency thấp, cần explainability cao hoặc không có dữ liệu tốt.
- RAG phù hợp khi cần trả lời theo tài liệu riêng, cập nhật thường xuyên và cần citation.
- Fine-tuning phù hợp khi cần thay đổi behavior/style/format hoặc domain pattern, không phải để "nhét kiến thức mới" thường xuyên.
- Agent phù hợp khi cần workflow nhiều bước và tool use, nhưng tăng rủi ro về latency, cost, security và khó debug.
- Production AI cần evaluation trước khi deploy, không chỉ demo vài câu hỏi đẹp.

## 1. Bản Đồ AI Cho Người Mới

Hãy xem AI như một cây phân cấp thực dụng:

```text
Artificial Intelligence
  -> Rule-based / search / optimization systems
  -> Machine Learning
      -> Classical ML: regression, tree, boosting, clustering
      -> Deep Learning
          -> CNN/RNN/Transformer
          -> Foundation models
              -> LLM
              -> Vision-language models
              -> Speech/audio models
  -> GenAI applications
      -> Prompting
      -> Structured output / tool calling
      -> RAG
      -> Agents / multi-agent workflows
      -> Fine-tuning / adapters
```

Giải thích ngắn:

| Thuật ngữ | Hiểu đơn giản | Ví dụ |
|---|---|---|
| AI | Hệ thống làm việc cần "trí tuệ" hoặc quyết định tự động | Search ranking, fraud detection, chatbot |
| Machine Learning | Model học pattern từ data thay vì viết rule tay | Churn prediction, spam detection |
| Deep Learning | ML dùng neural network nhiều layer | Image classification, speech recognition |
| Generative AI | AI tạo nội dung mới | Viết email, tạo code, tóm tắt tài liệu |
| LLM | Model ngôn ngữ lớn dự đoán/generate text | ChatGPT-style assistant, extraction |
| Embedding | Vector biểu diễn ý nghĩa của text/image | Semantic search |
| RAG | Retrieve tài liệu trước, rồi LLM trả lời dựa trên tài liệu | Hỏi đáp policy công ty có citation |
| Agent | LLM lập kế hoạch/gọi tool/đi qua workflow nhiều bước | Research assistant, coding assistant |
| Fine-tuning | Train thêm model trên dữ liệu riêng | Classifier tiếng Việt, format/style riêng |
| MLOps/LLMOps | Vận hành model/LLM trong production | tracking, eval, monitoring, rollback |

## 2. Vì Sao AI Bùng Nổ Nhưng Production Vẫn Khó?

AI bùng nổ vì 5 lực cùng xuất hiện:

1. Foundation model mạnh hơn, có thể xử lý text/code/image/audio.
2. API model giúp team nhỏ dùng model lớn mà không tự train.
3. GPU/cloud/inference runtime phát triển nhanh hơn.
4. Doanh nghiệp có nhiều dữ liệu nội bộ chưa khai thác tốt.
5. Developer tooling giúp build prototype rất nhanh.

Nhưng production khó vì prototype không đủ:

| Prototype dễ | Production khó |
|---|---|
| Chạy 5 prompt mẫu | Cần golden set và regression eval |
| Upload vài file PDF | Cần ingestion, versioning, permission, re-index |
| Model trả lời hay | Cần citation, no-answer, hallucination guardrail |
| Demo local | Cần auth, rate limit, logging, tracing, deployment |
| Cost không đáng kể | Cần cost/request, cache, model routing, budget |
| Một người maintain | Cần ownership, rollback, incident playbook |

Vì vậy khóa học này tập trung vào production engineering hơn là chỉ prompt hoặc notebook.

## 3. Cơ Hội Việc Làm AI Hiện Nay

Tín hiệu thị trường nên đọc theo hướng thận trọng:

- World Economic Forum Future of Jobs 2025 xếp AI and Machine Learning Specialists, Big Data Specialists và Software/Application Developers trong nhóm vai trò tăng trưởng nhanh đến 2030.
- U.S. Bureau of Labor Statistics dự báo Data Scientists tăng khoảng 34% giai đoạn 2024-2034, nhanh hơn nhiều so với trung bình toàn thị trường.
- Stanford AI Index 2026 cho thấy job postings có kỹ năng AI tăng ở nhiều sector, không chỉ công ty công nghệ; các skill như Python, data analysis, scalability, generative AI, RAG, LangGraph, agentic systems xuất hiện mạnh trong tin tuyển dụng AI.
- McKinsey State of AI 2025 mô tả adoption AI rộng hơn, agentic AI tăng, nhưng nhiều tổ chức vẫn gặp khó khi chuyển từ pilot sang scaled impact.

Nguồn tham khảo:

- WEF Future of Jobs 2025: https://www.weforum.org/publications/the-future-of-jobs-report-2025/in-full/2-jobs-outlook/
- BLS Data Scientists Outlook 2024-2034: https://www.bls.gov/ooh/math/data-scientists.htm
- Stanford AI Index 2026 Economy chapter: https://hai.stanford.edu/assets/files/ai_index_report_2026_chapter_4_economy.pdf
- McKinsey State of AI 2025: https://www.mckinsey.com/capabilities/quantumblack/our-insights/the-state-of-ai

Điều quan trọng: "AI Engineer" không phải một title cố định. Tin tuyển dụng có thể dùng nhiều tên:

| Title | Trọng tâm | Phù hợp với Senior SE? |
|---|---|---|
| AI Engineer | Build AI feature/app, tích hợp model, eval, deploy | Rất phù hợp |
| GenAI Engineer | LLM app, prompt, RAG, tool calling, agent | Rất phù hợp |
| LLM Application Engineer | API, orchestration, structured output, guardrails | Rất phù hợp |
| RAG Engineer | Ingestion, embedding, retrieval, reranking, citation | Rất phù hợp |
| ML Engineer | Train/deploy model, pipeline, feature, serving | Phù hợp nếu học thêm ML/DL |
| MLOps Engineer | Tracking, registry, serving, monitoring, infra | Rất phù hợp nếu mạnh DevOps |
| Data Scientist | Analysis, experiment, statistics, modeling | Phù hợp nếu thích data/statistics |
| AI Product Engineer | Build product workflow có AI | Phù hợp nếu mạnh full-stack/product |

Best solution cho người có nền tảng Senior SE: nhắm vào GenAI/RAG/LLM Production Engineer trước. Đây là giao điểm giữa backend/system design và AI hiện đại.

## 4. Ứng Dụng Thực Tế Của AI

AI có giá trị khi nó giảm cost, tăng tốc workflow, tăng chất lượng quyết định hoặc mở ra feature mới. Một số nhóm ứng dụng hiện thực tế nhất:

| Nhóm ứng dụng | Ví dụ | Kỹ thuật thường dùng |
|---|---|---|
| Knowledge assistant | Hỏi đáp tài liệu nội bộ, policy, SOP | RAG, citation, permission-aware retrieval |
| Customer support | Tóm tắt ticket, gợi ý trả lời, phân loại intent | LLM, classifier, retrieval |
| Developer productivity | Code assistant, test generation, review helper | LLM, tool calling, agent workflow |
| Document processing | Trích xuất invoice/contract/CV, chuẩn hóa JSON | OCR, LLM extraction, structured output |
| Search/recommendation | Semantic search, hybrid search, reranking | embedding, BM25, vector DB, reranker |
| Analytics assistant | Chat with data, report generation | SQL agent, BI integration, guardrails |
| Fraud/risk/churn | Prediction và prioritization | classical ML, tabular model, threshold tuning |
| Personalization | Recommendation, next-best-action | ranking model, feature store, experiment |
| Operations automation | Runbook assistant, incident summarization | RAG, tool calling, human approval |
| Compliance/security | PII detection, policy review, audit support | classifier, LLM, rule-based policy |

Không nên dùng AI chỉ vì "AI đang hot". Hãy dùng AI khi có ít nhất một trong các điều kiện:

- Rule thủ công quá nhiều và thay đổi liên tục.
- Input là ngôn ngữ tự nhiên, tài liệu, ảnh, audio hoặc dữ liệu khó viết rule.
- Cần ranking/prediction với xác suất chứ không chỉ đúng/sai.
- Có dữ liệu hoặc tài liệu đủ chất lượng.
- Có metric để đánh giá tốt/xấu.
- Có quy trình fallback khi model sai.

## 5. Vai Trò AI Engineer Thực Sự Làm Gì?

Một AI Engineer production thường làm các việc sau:

```text
business problem
  -> chọn approach: rule / ML / RAG / fine-tune / agent
  -> thiết kế data contract
  -> build pipeline hoặc orchestration
  -> tạo evaluation set và metric
  -> implement API/service
  -> add guardrails/security
  -> deploy + monitor latency/cost/quality
  -> iterate theo feedback thật
```

Deliverable thường gặp:

- API service gọi LLM an toàn, có structured output.
- RAG pipeline có ingestion, chunking, embedding, vector DB, reranking và citation.
- Evaluation pipeline có golden set, metrics và release gate.
- Dashboard/trace cho latency, token, cost, retrieval quality.
- Fine-tuning experiment có dataset, config, artifact và before/after eval.
- Guardrail layer cho prompt injection, PII, schema, tool permission.
- Technical design document có trade-off và rollback plan.

## 6. Skill Stack Cần Có

Với người mới nhưng đã biết IT/backend, học theo thứ tự này:

| Layer | Cần học | Vì sao |
|---|---|---|
| AI literacy | AI/ML/DL/LLM/RAG/Agent, failure modes | Để không chọn sai solution |
| Math đủ dùng | vector, matrix, probability, gradient | Để hiểu embedding, model score, training |
| Python ML stack | NumPy, Pandas, scikit-learn, PyTorch cơ bản | Để thực hành và đọc code ML |
| LLM app | prompt, structured output, function calling | Đây là nhu cầu phổ biến nhất hiện nay |
| RAG | chunking, embedding, vector DB, reranking, eval | Ứng dụng enterprise rất thực tế |
| Fine-tuning | dataset, LoRA/QLoRA, eval | Dùng khi RAG/prompt chưa đủ |
| Production | FastAPI, Docker, serving, monitoring, CI/CD | Lợi thế của Senior SE |
| Security | prompt injection, PII, ACL, guardrails | Bắt buộc cho enterprise |
| Product sense | metric, cost, UX, limitation | Để build feature có giá trị |

Những gì chưa cần đào sâu ngay:

- Prove theorem toán học.
- Tự train LLM từ đầu.
- Distributed training quy mô lớn.
- Paper mới mỗi tuần.
- Multi-agent phức tạp trước khi biết eval/guardrails.

## 7. Trade-off Quan Trọng Từ Ngày Đầu

| Quyết định | Option A | Option B | Best solution theo context |
|---|---|---|---|
| Rule vs AI | Rule dễ debug, rẻ, nhanh | AI linh hoạt hơn với input phức tạp | Bắt đầu bằng rule nếu rule ít và ổn định |
| Classical ML vs LLM | ML rẻ, nhanh, explainable hơn | LLM mạnh với ngôn ngữ/generation | Tabular prediction dùng ML trước; language workflow dùng LLM |
| RAG vs fine-tuning | RAG cập nhật knowledge tốt | Fine-tune đổi behavior/style tốt | Knowledge động dùng RAG; behavior riêng dùng fine-tune |
| Hosted model vs local model | Hosted mạnh, ít vận hành | Local kiểm soát data/cost dài hạn hơn | Prototype/quality dùng hosted; privacy/cost/latency đặc thù cân nhắc local |
| Agent vs workflow cố định | Agent linh hoạt | Workflow deterministic dễ test hơn | Bắt đầu deterministic, thêm agent khi thật sự cần |
| Optimize quality vs cost | Model lớn tốt hơn | Model nhỏ/cache rẻ hơn | Đặt metric và budget trước khi optimize |

## 8. Best Practices Ngay Từ Đầu

1. Luôn có baseline không-AI hoặc baseline đơn giản.
2. Viết input/output contract trước khi gọi model.
3. Tạo golden set nhỏ ngay từ prototype.
4. Đo latency, cost và quality cùng lúc.
5. Không log raw PII hoặc secret.
6. Không để model tự quyết quyền truy cập.
7. Với RAG, citation phải trỏ về chunk thật.
8. Với tool calling, tool phải allowlist, validate input và có idempotency nếu gây side effect.
9. Không dùng fine-tuning để cập nhật knowledge thay đổi hằng ngày.
10. Luôn ghi trade-off và limitation trong README/decision record.

## 9. Kiến Trúc Một AI Application Trong Production

Một ứng dụng AI production thường có nhiều lớp hơn một lệnh gọi model:

```text
Client/UI
  -> API Gateway / Backend API
      -> Auth / tenant / rate limit
      -> Request validation
      -> Policy layer / guardrails
      -> AI orchestrator
          -> Prompt builder
          -> Retriever: vector search / BM25 / metadata filter
          -> Reranker
          -> Model gateway
          -> Tool calling layer
          -> Output parser / schema validator
      -> Trace / metrics / audit log
      -> Feedback collector
      -> Offline evaluation pipeline
```

Không phải ứng dụng nào cũng cần toàn bộ thành phần. Tuy nhiên, một hệ thống dùng dữ liệu doanh nghiệp nên có tối thiểu:

- Auth và permission được kiểm tra trước retrieval hoặc tool execution.
- Input/output contract có version.
- Evaluation set có happy path, edge case và adversarial case.
- Trace đã redact PII và secret.
- Metric quality, latency và cost.
- Cách rollback prompt, model, retriever hoặc index.

Mental model quan trọng:

```text
Model quality cao
  != product quality cao
  != production readiness
```

Product quality còn phụ thuộc data, UX, fallback và evaluation. Production readiness còn phụ thuộc security, reliability, observability, cost và ownership.

## 10. Role Fit Và Skill Gap

### 10.1 Chọn vai trò mục tiêu

| Vai trò | Trọng tâm hằng ngày | Bằng chứng năng lực nên có |
|---|---|---|
| AI/GenAI Engineer | Build AI feature end-to-end | API + eval report + deployment + monitoring |
| RAG Engineer | Ingestion, retrieval, reranking, citation | RAG benchmark + permission-aware demo |
| ML Engineer | Training pipeline, feature, serving | Reproducible training + model artifact + serving |
| MLOps/LLMOps Engineer | Lifecycle, platform, observability | CI/CD + registry + canary/rollback + dashboard |
| Data Scientist | Analysis, experiment, statistics, modeling | Notebook/report có hypothesis và business insight |
| AI Product Engineer | Workflow và UX có AI | Sản phẩm end-to-end có feedback loop |

Với Senior Software Engineer, hướng chuyển đổi ngắn nhất thường là AI/GenAI Engineer, RAG Engineer hoặc MLOps/LLMOps Engineer. Đây là định hướng, không phải bảo đảm tuyển dụng; hãy đối chiếu với job description tại thị trường bạn muốn ứng tuyển.

### 10.2 Tự chấm skill

Chấm mỗi skill từ `0` đến `3`:

- `0`: chưa biết.
- `1`: giải thích được khái niệm.
- `2`: tự làm được bài tập nhỏ.
- `3`: làm được gần production và giải thích được trade-off.

| Skill | Điểm hiện tại | Evidence hiện có | Ngày học liên quan |
|---|---:|---|---|
| Python, NumPy, Pandas, scikit-learn |  |  | Day 2-8 |
| ML metrics và evaluation |  |  | Day 6-8 |
| PyTorch và Transformer |  |  | Day 9-17 |
| Prompt, structured output, tool calling |  |  | Day 18-24 |
| Fine-tuning và local LLM |  |  | Day 25-30 |
| RAG, vector search, reranking |  |  | Day 31-40 |
| Serving, Docker/K8s, observability |  |  | Day 41-45 |
| Guardrails, security, testing |  |  | Day 23, 46-47 |
| Technical writing và portfolio |  |  | Day 48-50 |

Output của bước này là năm skill gap quan trọng nhất cho role mục tiêu, không phải danh sách mọi thứ bạn chưa biết.

## 11. Bài Thực Hành: Chọn Hướng Đi Và Capstone

### Bước 1: Chọn một use case thật

Ưu tiên domain bạn đã hiểu, ví dụ:

- Hỏi đáp policy/SOP nội bộ có citation.
- Tóm tắt và phân loại ticket customer support.
- Trích xuất dữ liệu từ hợp đồng hoặc invoice sang JSON.
- Assistant cho runbook vận hành có human approval.
- Churn/fraud/risk scoring trên tabular data.

### Bước 2: Điền AI use-case canvas

| Câu hỏi | Câu trả lời của bạn |
|---|---|
| User cụ thể là ai? |  |
| Pain point hiện tại là gì? |  |
| Workflow nào đang tốn thời gian hoặc chi phí? |  |
| Input và output mong muốn là gì? |  |
| Output sai gây hậu quả gì? |  |
| Dữ liệu/tài liệu có ở đâu, ai sở hữu? |  |
| Có PII, secret hoặc permission boundary không? |  |
| Baseline không-AI là gì? |  |
| Metric business và metric kỹ thuật là gì? |  |
| Fallback khi AI không chắc là gì? |  |

### Bước 3: Chọn approach nhỏ nhất giải quyết được bài toán

```text
Rule rõ, ít thay đổi?
  -> rule / SQL / search truyền thống

Prediction trên tabular data?
  -> classical ML baseline

Hiểu hoặc tạo ngôn ngữ tự nhiên?
  -> LLM với structured output nếu có schema

Trả lời theo tài liệu riêng, thay đổi thường xuyên?
  -> RAG

Workflow có nhiều bước hoặc gọi tool?
  -> deterministic workflow trước; agent khi thật sự cần
```

Ghi quyết định vào bảng:

| Approach | Phù hợp? | Lý do | Risk chính |
|---|---|---|---|
| Rule/SQL/search thường |  |  |  |
| Classical ML |  |  |  |
| LLM prompt-only |  |  |  |
| RAG |  |  |  |
| Fine-tuning |  |  |  |
| Agent/tool calling |  |  |  |

### Bước 4: Viết mini decision record

Tạo ghi chú cá nhân theo cấu trúc:

```markdown
# Day 00 - AI Direction

## Target role

## Top 5 skill gaps và evidence hiện tại

## Candidate capstone
- User:
- Problem:
- Baseline:
- Chosen approach:
- Vì sao chưa chọn các approach khác:
- Data/document source:
- Evaluation metrics:
- Production risks:
- Fallback:

## Deliverable sau 50 ngày
```

Tiêu chí hoàn thành: người khác đọc decision record phải hiểu bạn đang giải quyết vấn đề gì, vì sao cần AI, cách đo thành công và điều gì xảy ra khi AI sai.

## 12. Quiz Tự Kiểm Tra

1. Vì sao LLM không nên được xem như database?
2. Khi nào RAG phù hợp hơn fine-tuning?
3. AI Engineer khác Data Scientist ở deliverable chính nào?
4. Vì sao production AI cần evaluation set ngoài unit test?
5. Khi nào rule hoặc search truyền thống tốt hơn LLM?
6. Agent có trade-off gì so với workflow deterministic?
7. Senior Software Engineer có lợi thế và skill gap nào khi chuyển sang AI Engineer?

<details>
<summary>Gợi ý đáp án</summary>

1. LLM sinh token theo xác suất, có thể hallucinate và không cung cấp freshness/citation như một data store được quản lý.
2. Khi knowledge nằm trong tài liệu riêng, thay đổi thường xuyên và cần citation hoặc permission-aware retrieval.
3. AI Engineer chủ yếu đưa AI feature/service vào sản phẩm; Data Scientist thường tập trung analysis, experiment, statistics và modeling.
4. AI output có tính xác suất; evaluation set đo quality trên phân phối case đại diện và phát hiện regression.
5. Khi logic rõ, deterministic, latency/cost thấp và explainability quan trọng hơn khả năng hiểu ngôn ngữ mở.
6. Agent linh hoạt hơn nhưng khó test/debug hơn, latency/cost cao hơn và tăng rủi ro tool misuse.
7. Lợi thế là system design, API, security, observability và deployment; gap thường là data/evaluation, ML fundamentals, retrieval và model failure modes.

</details>

## 13. Lộ Trình 50 Ngày Nối Với Day 00 Như Thế Nào?

```text
Day 00: thấy toàn cảnh nghề và sản phẩm AI
Day 01-08: ML foundation để hiểu data/model/eval
Day 09-16: Deep Learning/NLP/Transformer để hiểu nền của LLM
Day 17-24: LLM application engineering
Day 25-30: Fine-tuning và local LLM
Day 31-40: Production RAG
Day 41-47: MLOps, serving, observability, cost, guardrails, CI
Day 48-50: Capstone và portfolio
```

Nếu bạn chỉ học để "biết dùng ChatGPT", lộ trình này quá sâu. Nếu bạn muốn chuyển từ Senior SE sang AI Engineer có khả năng build production system, lộ trình này đi đúng trọng tâm.

## 14. Dùng Được Trong Production Không?

Bài Day 00 không phải implementation, nhưng mindset và decision framework dùng được trong production discovery.

Điều kiện để áp dụng:

- Có problem statement rõ, không bắt đầu từ model.
- Có user workflow cụ thể.
- Có dữ liệu/tài liệu thật hoặc plan thu thập dữ liệu.
- Có metric business và metric kỹ thuật.
- Có risk classification: low, medium, high impact.
- Có fallback/human review cho case rủi ro.
- Có owner cho vận hành sau khi demo.

## 15. Nguồn Và Cách Đọc Số Liệu Thị Trường

Các số liệu dưới đây được kiểm tra ngày **8 tháng 6 năm 2026**. Chúng cho biết xu hướng, không bảo đảm một title hoặc kỹ năng cụ thể sẽ có nhu cầu như nhau ở mọi quốc gia:

- [World Economic Forum, Future of Jobs Report 2025](https://www.weforum.org/publications/the-future-of-jobs-report-2025/in-full/2-jobs-outlook/): Big Data Specialists, AI and Machine Learning Specialists, Software and Applications Developers nằm trong nhóm vai trò tăng nhanh đến năm 2030.
- [U.S. Bureau of Labor Statistics, Data Scientists](https://www.bls.gov/ooh/math/data-scientists.htm): dự báo việc làm Data Scientist tại Hoa Kỳ tăng 34% trong giai đoạn 2024-2034.
- [Stanford AI Index 2026, Economy](https://hai.stanford.edu/ai-index/2026-ai-index-report/economy): tổng hợp đầu tư, adoption, productivity và thay đổi kỹ năng/job posting liên quan AI.
- [McKinsey, State of AI 2025](https://www.mckinsey.com/capabilities/quantumblack/our-insights/the-state-of-ai): khảo sát cho thấy agentic AI được thử nghiệm rộng nhưng tác động EBIT quy mô toàn doanh nghiệp còn hạn chế.

Best practice khi định hướng nghề nghiệp:

1. Thu thập 20-30 job description mới nhất tại thị trường mục tiêu.
2. Chuẩn hóa skill thành nhóm: foundation, application, data, platform, security, product.
3. Đếm tần suất nhưng đọc cả seniority và domain context.
4. Chọn một portfolio project chứng minh được nhiều skill cốt lõi.
5. Lặp lại khảo sát trước khi ứng tuyển; không học chỉ theo một báo cáo toàn cầu.

## Checklist Hoàn Thành

- [ ] Tôi phân biệt được AI, ML, DL, GenAI, LLM, RAG và Agent.
- [ ] Tôi biết ít nhất 5 ứng dụng AI thực tế trong doanh nghiệp.
- [ ] Tôi giải thích được AI Engineer khác ML Engineer và Data Scientist.
- [ ] Tôi biết vì sao Senior SE có lợi thế khi làm production AI.
- [ ] Tôi chọn được target role gần nhất với mình.
- [ ] Tôi có danh sách skill gap cá nhân.
- [ ] Tôi có ý tưởng capstone đầu tiên và biết metric cần đo.
- [ ] Tôi biết khi nào không nên dùng AI.
- [ ] Tôi đã viết mini decision record cho capstone.
- [ ] Tôi trả lời được ít nhất 6/7 câu quiz mà không nhìn gợi ý.
