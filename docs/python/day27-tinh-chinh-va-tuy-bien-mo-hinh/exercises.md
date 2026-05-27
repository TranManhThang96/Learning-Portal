# Bài Tập — Ngày 27: Fine-tuning & Model Customization

## Bài 1 — Strategy Decision Tool (Cơ bản)

**Mô tả:** Xây dựng một CLI tool interactive giúp người dùng quyết định nên dùng Prompt Engineering, RAG hay Fine-tuning cho use case của họ.

**Yêu cầu:**
1. Hỏi người dùng một loạt câu hỏi Yes/No về use case (ít nhất 6 câu hỏi):
   - Dữ liệu có nhạy cảm không?
   - Dataset có sẵn có đủ 100+ examples không?
   - Kiến thức domain có thay đổi thường xuyên không?
   - Cần output style/format cụ thể không?
   - Có GPU/budget cho training không?
   - Cần latency < 1 giây không?
2. Dựa trên câu trả lời, tính điểm cho mỗi strategy và recommend strategy có điểm cao nhất
3. In ra explanation chi tiết TẠI SAO strategy đó được recommend
4. In ra **danh sách action items** tiếp theo (ví dụ: nếu chọn RAG → "1. Thiết lập vector DB, 2. Chuẩn bị documents...")
5. Export `decision.md` theo format: use case summary, scores, chosen strategy, metrics cần đo, rollback plan

**Expected output:**
```
=== AI Strategy Advisor ===

Trả lời các câu hỏi sau (y/n):

[1/6] Dữ liệu của bạn có chứa thông tin nhạy cảm (PII, secrets)? y
[2/6] Bạn có dataset training 100+ examples không? n
...

=== Kết quả phân tích ===

Scores:
  Prompt Engineering: 35/100
  RAG:                65/100  ← RECOMMENDED
  Fine-tuning:        20/100

📌 Recommendation: RAG (Retrieval Augmented Generation)

Lý do:
  ✓ Dữ liệu nhạy cảm → cần kiểm soát data
  ✓ Dataset nhỏ → không đủ để fine-tune
  ...

📋 Action Items:
  1. Setup vector database (Qdrant hoặc ChromaDB)
  2. Chunking và indexing documents
  ...
```

**Hint:**
- Dùng `input("...").strip().lower() in ['y', 'yes']` để parse Yes/No
- Điểm mỗi câu trả lời bằng dict: `scores = {"prompt_engineering": 0, "rag": 0, "fine_tuning": 0}`
- `max(scores, key=scores.get)` để tìm strategy điểm cao nhất

---

## Bài 2 — Dataset Quality Analyzer (Trung bình)

**Mô tả:** Xây dựng tool phân tích chất lượng dataset cho instruction fine-tuning, đưa ra báo cáo chi tiết và gợi ý cải thiện.

**Yêu cầu:**

1. Đọc dataset từ file JSONL (mỗi dòng là 1 JSON object)
2. Phân tích và báo cáo:
   - Tổng số examples, sau khi lọc còn bao nhiêu
   - Distribution của instruction length (histogram bằng text)
   - Distribution của output length
   - Số lượng và % duplicates (exact match)
   - Top 10 most common words trong instructions
   - Phát hiện anomalies: examples quá ngắn (<5 words) hoặc quá dài (>300 words)
3. Quality score từ 0-100 dựa trên các tiêu chí
4. Suggest improvements cụ thể

**Sample dataset để tạo (`sample_dataset.jsonl`):**
```json
{"instruction": "What is Python?", "output": "Python is a programming language."}
{"instruction": "Explain decorators", "output": "Decorators wrap functions to add behavior. Example: @property, @staticmethod"}
{"instruction": "What is Python?", "output": "Python is created by Guido van Rossum."}
{"instruction": "Write hello world", "output": "print('Hello, World!')"}
{"instruction": "hi", "output": "hello"}
{"instruction": "Explain the concept of object-oriented programming in Python including classes, inheritance, polymorphism, encapsulation and abstraction with detailed examples for each concept", "output": "OOP is a paradigm..."}
```

**Expected output:**
```
=== Dataset Quality Report ===
File: sample_dataset.jsonl

📊 Basic Statistics:
  Total examples:     6
  Valid examples:     5 (83.3%)
  Removed (too short): 1 (16.7%)

📏 Instruction Length Distribution:
  1-5 words:   ██ (2)
  6-10 words:  ████ (3)
  11-20 words: (0)
  21+ words:   █ (1)

🔄 Duplicates:
  Exact duplicates: 1 (16.7%)
  Affected examples: "What is Python?" appears 2 times

⭐ Quality Score: 62/100
  - Diversity: 70/100
  - Length distribution: 55/100
  - Duplicate rate: 60/100

💡 Suggestions:
  1. Remove 1 duplicate instruction
  2. Add more diverse examples (variety of instruction types)
  3. Short example "hi/hello" may not add value
```

**Hint:**
- Đọc JSONL: `[json.loads(line) for line in open('file.jsonl')]`
- Text histogram: `"█" * count + f" ({count})"`
- `Counter(words)` từ `collections` cho word frequency
- Tạo JSONL test file bằng code trong script

---

## Bài 3 — Mini Fine-tuning Pipeline với Evaluation (Nâng cao / Challenge)

**Mô tả:** Xây dựng pipeline có thể chạy local cho data/evaluation, kèm phần fine-tuning GPT-2 với LoRA ở chế độ optional smoke test. Không kỳ vọng chạy full training trong buổi học 2 giờ.

**Yêu cầu:**

1. **Tạo training/eval data:** 20 examples Python Q&A (hardcode, không cần download), split train/validation/test.
2. **Runnable local eval lab (bắt buộc):**
   - Tạo baseline outputs bằng mock generator hoặc GPT-2 base nếu máy đủ nhanh
   - Tính ROUGE-1, ROUGE-2, ROUGE-L giữa references và hypotheses
   - Tính quality report: missing answers, duplicate prompts, average output length
3. **Setup LoRA (đọc hiểu hoặc smoke test):** Config LoRA với `r=4`, `lora_alpha=16` cho GPT-2.
4. **Optional micro-training:** Nếu có thời gian/hardware, chạy `max_steps=5-10`, batch size 1. Mục tiêu là verify pipeline chạy, không phải cải thiện metric rõ ràng.
5. **So sánh outputs:** Với cùng prompt, in side-by-side output của baseline/mock vs optional fine-tuned model.
6. **Visualization bằng text:** Vẽ training/eval curve bằng text characters nếu có training run; nếu không, vẽ score table của baseline eval.

**Expected output (partial):**
```
=== Fine-tuning Pipeline ===

📦 Data Preparation:
  Training examples: 16
  Validation examples: 2
  Test examples: 2

🔧 Model Setup:
  Base model: gpt2
  Trainable params: 294,912 (0.24%)
  Total params: 124,734,720

🏋️ Training:
  Epoch 1/3: loss=3.245 ████████████████████ 100%
  Epoch 2/3: loss=2.891 ████████████████████ 100%
  Epoch 3/3: loss=2.456 ████████████████████ 100%

📊 Evaluation Results:
  Metric          Before    After    Change
  Perplexity      89.3      52.1     -41.7% ✅
  ROUGE-1 F1      0.142     0.289    +103%  ✅
  ROUGE-2 F1      0.021     0.087    +314%  ✅

🔍 Output Comparison:
  Prompt: "### Instruction:\nWhat is a decorator?\n\n### Response:\n"

  Base Model:
    "The decorator pattern is commonly used in..."  (generic)

  Fine-tuned:
    "A decorator is a function that wraps another function..."  (domain-specific)
```

**Hint:**
- Required path không cần GPU: build dataset → generate/mock hypotheses → compute ROUGE → in report.
- Training loop optional: sau mỗi epoch hoặc mỗi `logging_steps`, evaluate trên validation set và log loss.
- Text loss curve: `"▪" * int((3 - loss) * 10)` để visualize
- Side-by-side comparison: sử dụng `zip` và format string để align output
- Nếu không có GPU, dùng `torch.device("cpu")` và batch_size=1

**Lưu ý:** Bài này cần `uv add transformers peft datasets accelerate rouge-score torch`. Phần eval chạy local. Phần training CPU chỉ là smoke test và có thể mất lâu hơn 3-5 phút tùy máy; bỏ qua nếu laptop yếu.

---

## 🔍 Gợi ý kiểm tra kết quả

**Bài 1:**
- Thử các combinations khác nhau — mỗi path phải cho kết quả khác nhau
- Edge case: trả lời "n" cho tất cả → nên recommend Prompt Engineering
- Edge case: có data lớn + GPU → nên recommend Fine-tuning

**Bài 2:**
- Tạo JSONL file với ít nhất 20 examples, bao gồm intentional duplicates và bad examples
- Quality score phải giảm khi thêm nhiều duplicates
- Suggestions phải cụ thể, không generic

**Bài 3:**
- Required: script eval chạy xong không cần API key/GPU và in ROUGE table hợp lệ
- Optional training: nếu chạy, log `max_steps`, device, trainable params và checkpoint path
- Không bắt buộc perplexity/ROUGE sau fine-tune phải tốt hơn baseline trong smoke test nhỏ

**Kiểm tra cài đặt:**
```bash
python -c "from peft import LoraConfig; print('PEFT OK')"
python -c "from rouge_score import rouge_scorer; print('rouge-score OK')"
python -c "import torch; print(f'PyTorch {torch.__version__}')"
```
