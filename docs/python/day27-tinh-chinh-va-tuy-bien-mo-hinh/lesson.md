# Ngày 27: Fine-tuning & Model Customization

## ⚠️ Lưu ý thực tế cho bài này

**Fine-tuning thực tế cần GPU (Colab Pro/RunPod) và 2-4 giờ training time.**
**Bài này focus vào: Understanding + Decision Making + Dataset Preparation (có thể chạy) + Code walkthrough (không expect chạy full).**

Scope contract cho learner:
- **Bắt buộc chạy local:** decision tool, dataset preparation/quality analyzer, và evaluation metrics trên sample outputs.
- **Đọc hiểu hoặc dry-run:** PEFT/LoRA training code. Không yêu cầu full fine-tuning model lớn trong 2 giờ.
- **Optional GPU lab:** chỉ chạy khi có GPU/budget; dùng `max_steps` nhỏ để kiểm tra pipeline thay vì kỳ vọng model cải thiện thật.

Phân bổ thời gian gợi ý:
- 40 phút: Theory — khi nào fine-tune vs RAG vs prompt engineering (decision tree)
- 20 phút: Code walkthrough — LoRA fine-tuning code (đọc hiểu, không chạy full)
- 30 phút: Hands-on — dataset preparation với Pydantic (CÓ THỂ chạy)
- 30 phút: Bài tập — evaluate pre-trained model với BLEU/ROUGE

## 🎯 Mục tiêu học tập
- Phân tích được khi nào nên fine-tune vs RAG vs prompt engineering
- Hiểu cơ chế LoRA/QLoRA và cách dùng thư viện PEFT (đọc code, không cần chạy)
- Chuẩn bị dataset đúng format cho fine-tuning (THỰC HÀNH)
- Đánh giá model với các metrics BLEU, ROUGE (dùng pre-trained model)

## 🔄 So sánh với NodeJS

| Khái niệm | NodeJS/TypeScript | Python ML |
|-----------|-------------------|-----------|
| Customization | Config objects, middleware | Fine-tuning, prompt engineering |
| "Training data" | N/A | Dataset (JSONL, CSV, HuggingFace datasets) |
| "Model version" | Package version (semver) | Checkpoint (epoch-1, epoch-2...) |
| Evaluation | Unit test pass/fail | Metrics (BLEU, ROUGE, accuracy) |
| "Overfitting" | N/A | Model học thuộc training data, không generalize |
| Memory optimization | N/A | Gradient checkpointing, mixed precision |
| Iterative improvement | Code refactor | Fine-tune → evaluate → repeat |

Fine-tuning là quá trình "dạy thêm" cho model đã có sẵn kiến thức. Tương tự như bạn hire một senior dev và onboard họ vào domain của công ty — họ đã có kỹ năng chung, chỉ cần học thêm context cụ thể.

## 📖 Lý thuyết

### 1. Khi nào Fine-tune vs RAG vs Prompt Engineering

**WHY:** Ba phương pháp khác nhau về cost, complexity và effectiveness. Chọn sai → lãng phí thời gian và tiền bạc.

```python
# Framework để quyết định strategy
from dataclasses import dataclass

@dataclass
class ProblemProfile:
    # Về data
    has_proprietary_knowledge: bool    # công ty có kiến thức riêng không?
    knowledge_changes_frequently: bool # kiến thức thay đổi thường xuyên?
    dataset_size: int                  # số examples có sẵn để train

    # Về yêu cầu
    needs_specific_style: bool         # cần viết theo style cụ thể?
    needs_specific_format: bool        # cần output format cụ thể?
    latency_critical: bool             # latency < 500ms?

    # Về resources
    has_ml_expertise: bool             # team có ML knowledge?
    budget_for_training: bool          # có budget GPU training?

def recommend_strategy(p: ProblemProfile) -> dict:
    """
    Decision framework cho customization strategy.
    Thứ tự ưu tiên: Prompt Engineering → RAG → Fine-tuning
    (từ đơn giản đến phức tạp)
    """

    # Thử Prompt Engineering trước — miễn phí, nhanh nhất
    if not p.has_proprietary_knowledge and not p.needs_specific_style:
        return {
            "strategy": "Prompt Engineering",
            "effort": "Thấp (giờ → ngày)",
            "cost": "Chỉ tốn token",
            "reason": "Vấn đề có thể giải quyết bằng cách mô tả rõ trong prompt",
            "example": "Few-shot examples, chain-of-thought, structured output"
        }

    # RAG nếu có knowledge riêng và thường xuyên thay đổi
    if p.has_proprietary_knowledge and p.knowledge_changes_frequently:
        return {
            "strategy": "RAG (Retrieval Augmented Generation)",
            "effort": "Trung bình (tuần)",
            "cost": "Embedding API + vector DB",
            "reason": "Kiến thức thay đổi thường xuyên → fine-tune sẽ outdated nhanh",
            "example": "Internal docs, product catalog, real-time data"
        }

    # Fine-tuning khi cần style/behavior cụ thể + đủ data
    if (p.needs_specific_style or p.needs_specific_format) and p.dataset_size >= 100:
        if not p.has_ml_expertise:
            return {
                "strategy": "Fine-tuning với PEFT/LoRA (managed service)",
                "effort": "Cao (tuần → tháng)",
                "cost": "GPU rental + inference cost",
                "reason": "Cần style cụ thể mà prompt không đạt được, dùng OpenAI fine-tuning cho đơn giản",
                "example": "Customer service tone, code generation in company style"
            }
        return {
            "strategy": "Fine-tuning với LoRA/QLoRA",
            "effort": "Cao (tuần → tháng)",
            "cost": "GPU + thời gian",
            "reason": "Cần style cụ thể, có đủ data và expertise",
            "example": "Medical QA, legal document, domain-specific code"
        }

    # Fallback: RAG là safe default
    return {
        "strategy": "RAG",
        "effort": "Trung bình",
        "cost": "Trung bình",
        "reason": "Default safe choice khi không chắc chắn"
    }

# Test scenarios
scenarios = [
    ("Chatbot trả lời FAQ công ty (data thay đổi mỗi tháng)",
     ProblemProfile(True, True, 500, False, False, False, False, False)),

    ("Code generator theo code style của team",
     ProblemProfile(True, False, 1000, True, True, True, True, True)),

    ("Tóm tắt legal documents",
     ProblemProfile(False, False, 50, True, True, False, False, False)),

    ("General Q&A chatbot",
     ProblemProfile(False, False, 0, False, False, False, False, False)),
]

for name, profile in scenarios:
    rec = recommend_strategy(profile)
    print(f"\n📌 Use case: {name}")
    print(f"   Strategy: {rec['strategy']}")
    print(f"   Effort:   {rec['effort']}")
    print(f"   Reason:   {rec['reason']}")
```

**Printable decision artifact:** Với team thật, lưu quyết định vào Markdown để review cùng product/infra trước khi thuê GPU.

```markdown
# AI Customization Decision

## Use case
- Goal:
- Users:
- Data sensitivity:
- Freshness requirement:

## Options considered
| Option | Fit | Cost | Risk |
|--------|-----|------|------|
| Prompt engineering | | | |
| RAG | | | |
| Fine-tuning | | | |

## Decision
- Chosen strategy:
- Why:
- What we will measure:
- Rollback plan:
```

### 2. LoRA/QLoRA Basics với PEFT

**WHY:** Fine-tuning toàn bộ model 7B thường cần VRAM lớn, pipeline dữ liệu sạch và thời gian thử nghiệm đáng kể. LoRA (Low-Rank Adaptation) chỉ train thêm adapter nhỏ thay vì update toàn bộ weight, nên giảm mạnh số trainable parameters; chất lượng có thể rất cạnh tranh nhưng vẫn phải đo bằng eval thật, không được assume "gần bằng full fine-tune" cho mọi domain.

**HOW — Cơ chế LoRA:**

```python
# Giải thích LoRA bằng code trực quan
import numpy as np

# Model gốc có weight matrix W (frozen, không thay đổi)
# LoRA thêm: W' = W + BA
# Trong đó B và A là ma trận nhỏ (rank r << dimension)

def demonstrate_lora_concept():
    """Minh họa cơ chế LoRA với numpy"""

    d_model = 768      # dimension của transformer
    rank = 8           # LoRA rank (hyperparameter, thường 4-64)

    # Ma trận weight gốc (frozen)
    W_original = np.random.randn(d_model, d_model) * 0.02

    # LoRA matrices (trainable)
    A = np.random.randn(rank, d_model) * 0.01   # A: rank × d_model
    B = np.zeros((d_model, rank))                # B: d_model × rank (khởi tạo = 0)

    # Adapter = B @ A (rank decomposition)
    # Ban đầu B=0, nên delta W = 0 (không ảnh hưởng đến inference ban đầu)
    delta_W = B @ A

    # Weight mới = weight gốc + adapter
    W_adapted = W_original + delta_W

    # Thống kê params
    original_params = d_model * d_model
    lora_params = rank * d_model + d_model * rank  # A + B
    ratio = lora_params / original_params * 100

    print(f"Weight matrix W: {d_model}×{d_model} = {original_params:,} params")
    print(f"LoRA A matrix:   {rank}×{d_model} = {rank*d_model:,} params")
    print(f"LoRA B matrix:   {d_model}×{rank} = {d_model*rank:,} params")
    print(f"LoRA total:      {lora_params:,} params ({ratio:.1f}% của W)")
    print(f"\nNếu model 7B có ~200 attention layers:")
    print(f"Full fine-tune: ~7,000,000,000 trainable params")
    print(f"LoRA (r=8):    ~{200 * lora_params:,} trainable params")
    print(f"Reduction:     ~{7_000_000_000 / (200 * lora_params):.0f}x ít hơn")

demonstrate_lora_concept()
```

```python
# === PEFT LoRA FINE-TUNING THỰC TẾ ===
# uv add transformers peft datasets accelerate bitsandbytes
# Walkthrough, không phải phần bắt buộc chạy full trong 2 giờ.
# Nếu chỉ smoke test local: dùng GPT-2 nhỏ, max_steps=5-10, batch_size=1.

from transformers import (
    AutoTokenizer,
    AutoModelForCausalLM,
    TrainingArguments,
    Trainer,
    DataCollatorForSeq2Seq
)
from peft import LoraConfig, get_peft_model, TaskType
from datasets import Dataset
import torch

# Dùng model nhỏ cho demo (GPT-2)
MODEL_NAME = "gpt2"  # thực tế dùng "meta-llama/Llama-3.2-3B" hoặc "mistralai/Mistral-7B-v0.1"

print(f"Loading tokenizer and model: {MODEL_NAME}")
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
tokenizer.pad_token = tokenizer.eos_token  # GPT-2 không có pad token

# Load model bình thường (không quantize vì dùng GPT-2 nhỏ)
model = AutoModelForCausalLM.from_pretrained(
    MODEL_NAME,
    torch_dtype=torch.float32,  # float16 nếu có GPU
)

# === CẤU HÌNH LORA ===
lora_config = LoraConfig(
    task_type=TaskType.CAUSAL_LM,  # loại task: causal language modeling
    r=8,                            # rank — càng lớn càng nhiều params nhưng chất lượng tốt hơn
    lora_alpha=32,                  # scaling factor (thường = 2*r đến 4*r)
    lora_dropout=0.1,               # dropout để tránh overfitting
    target_modules=["c_attn"],      # layers để apply LoRA (GPT-2 specific)
    # Với LLaMA: target_modules=["q_proj", "v_proj", "k_proj", "o_proj"]
    bias="none",                    # không train bias
)

# Wrap model với LoRA
model = get_peft_model(model, lora_config)

# Kiểm tra số params trainable
model.print_trainable_parameters()
# Output: trainable params: 294,912 || all params: 124,734,720 || trainable%: 0.24
```

```python
# === CHUẨN BỊ DATASET ĐƠN GIẢN ===
from datasets import Dataset

# Dữ liệu training — format instruction tuning
training_examples = [
    {
        "instruction": "Giải thích Python decorator",
        "response": "Decorator là function bọc ngoài function khác để thêm behavior. Dùng @syntax."
    },
    {
        "instruction": "Viết list comprehension từ 0 đến 9",
        "response": "[x for x in range(10)]"
    },
    {
        "instruction": "Tạo dictionary từ hai lists",
        "response": "Dùng zip: dict(zip(keys, values))"
    },
    # Thực tế cần ít nhất 100-1000 examples
]

def format_example(example: dict) -> dict:
    """Format thành prompt/completion pair"""
    # Alpaca-style prompt format
    text = f"### Instruction:\n{example['instruction']}\n\n### Response:\n{example['response']}"
    return {"text": text}

dataset = Dataset.from_list([format_example(e) for e in training_examples])
print(f"Dataset size: {len(dataset)}")
print(f"Example:\n{dataset[0]['text']}")

# Tokenize
def tokenize_function(examples):
    tokenized = tokenizer(
        examples["text"],
        truncation=True,
        max_length=512,
        padding="max_length"
    )
    # Labels = input_ids (causal LM predict next token)
    tokenized["labels"] = tokenized["input_ids"].copy()
    return tokenized

tokenized_dataset = dataset.map(tokenize_function, batched=True)
tokenized_dataset = tokenized_dataset.remove_columns(["text"])
tokenized_dataset.set_format("torch")
```

```python
# === TRAINING ===
from transformers import TrainingArguments, Trainer

training_args = TrainingArguments(
    output_dir="./lora-finetuned-gpt2",
    num_train_epochs=3,
    max_steps=10,                       # smoke test; bỏ dòng này khi train thật
    per_device_train_batch_size=1,
    gradient_accumulation_steps=4,   # effective batch = 1*4 = 4 trong smoke test
    learning_rate=3e-4,               # LoRA thường dùng LR cao hơn full fine-tune
    warmup_steps=50,
    logging_steps=10,
    save_steps=100,
    fp16=torch.cuda.is_available(),  # dùng mixed precision nếu có GPU
    optim="adamw_torch",
    report_to="none",                 # tắt WandB logging
)

trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=tokenized_dataset,
    data_collator=lambda data: {
        'input_ids': torch.stack([f['input_ids'] for f in data]),
        'attention_mask': torch.stack([f['attention_mask'] for f in data]),
        'labels': torch.stack([f['labels'] for f in data]),
    }
)

# Bắt đầu training (sẽ chạy nhanh vì GPT-2 nhỏ và ít data)
print("Starting training...")
trainer.train()

# Lưu chỉ LoRA weights (rất nhỏ, vài MB)
model.save_pretrained("./lora-adapter")
tokenizer.save_pretrained("./lora-adapter")
print("Saved LoRA adapter to ./lora-adapter")
```

```python
# === LOAD VÀ DÙNG MODEL ĐÃ FINE-TUNE ===
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch

def load_finetuned_model(base_model: str, adapter_path: str):
    """Load base model + LoRA adapter"""
    tokenizer = AutoTokenizer.from_pretrained(adapter_path)

    # Load base model (frozen)
    base = AutoModelForCausalLM.from_pretrained(base_model, torch_dtype=torch.float32)

    # Load và merge LoRA adapter
    model = PeftModel.from_pretrained(base, adapter_path)

    # Optional: merge adapter vào model để inference nhanh hơn
    # model = model.merge_and_unload()  # không thể unload sau này

    return model, tokenizer

def generate_response(model, tokenizer, instruction: str, max_new_tokens: int = 100) -> str:
    prompt = f"### Instruction:\n{instruction}\n\n### Response:\n"

    inputs = tokenizer(prompt, return_tensors="pt")

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            temperature=0.7,
            do_sample=True,
            pad_token_id=tokenizer.eos_token_id
        )

    # Decode và bỏ phần prompt
    full_text = tokenizer.decode(outputs[0], skip_special_tokens=True)
    response = full_text[len(prompt):]
    return response.strip()

# Test
# model, tokenizer = load_finetuned_model("gpt2", "./lora-adapter")
# response = generate_response(model, tokenizer, "Giải thích Python decorator")
# print(f"Response: {response}")
```

### 3. Dataset Preparation

**WHY:** "Garbage in, garbage out" — chất lượng dataset quan trọng hơn nhiều so với chọn model hay hyperparameter. 80% công việc fine-tuning là data preparation.

```python
# === PIPELINE CHUẨN BỊ DATASET ===
import json
import random
from typing import Optional
from datasets import Dataset, DatasetDict

def prepare_instruction_dataset(
    raw_examples: list[dict],
    train_ratio: float = 0.8,
    val_ratio: float = 0.1,
    # test_ratio = 1 - train_ratio - val_ratio = 0.1
    seed: int = 42
) -> DatasetDict:
    """
    Chuẩn bị dataset cho instruction fine-tuning.

    raw_examples format:
    [{"instruction": "...", "input": "...", "output": "..."}]
    input là optional context/data
    """
    random.seed(seed)

    # 1. Validate và clean data
    cleaned = []
    skipped = 0

    for ex in raw_examples:
        # Kiểm tra required fields
        if not ex.get("instruction") or not ex.get("output"):
            skipped += 1
            continue

        # Loại bỏ examples quá ngắn hoặc quá dài
        instruction_len = len(ex["instruction"].split())
        output_len = len(ex["output"].split())

        if instruction_len < 3 or output_len < 2:
            skipped += 1
            continue

        if instruction_len > 200 or output_len > 500:
            skipped += 1
            continue

        cleaned.append(ex)

    print(f"Raw: {len(raw_examples)}, Cleaned: {len(cleaned)}, Skipped: {skipped}")

    # 2. Format thành Alpaca format
    def format_alpaca(example: dict) -> dict:
        """Alpaca instruction format"""
        if example.get("input"):
            prompt = (
                f"Below is an instruction with context. "
                f"Write a response.\n\n"
                f"### Instruction:\n{example['instruction']}\n\n"
                f"### Input:\n{example['input']}\n\n"
                f"### Response:\n{example['output']}"
            )
        else:
            prompt = (
                f"Below is an instruction. "
                f"Write a response.\n\n"
                f"### Instruction:\n{example['instruction']}\n\n"
                f"### Response:\n{example['output']}"
            )
        return {"text": prompt}

    formatted = [format_alpaca(ex) for ex in cleaned]

    # 3. Shuffle và split
    random.shuffle(formatted)
    n = len(formatted)
    train_end = int(n * train_ratio)
    val_end = train_end + int(n * val_ratio)

    splits = DatasetDict({
        "train": Dataset.from_list(formatted[:train_end]),
        "validation": Dataset.from_list(formatted[train_end:val_end]),
        "test": Dataset.from_list(formatted[val_end:])
    })

    print(f"\nDataset splits:")
    for split, ds in splits.items():
        print(f"  {split}: {len(ds)} examples")

    return splits

# Test với sample data
sample_data = [
    {"instruction": "Translate to Vietnamese", "input": "Hello world", "output": "Xin chào thế giới"},
    {"instruction": "Write a Python function to add two numbers", "input": "", "output": "def add(a, b):\n    return a + b"},
    {"instruction": "Explain what a variable is", "input": "", "output": "A variable is a named storage location in memory."},
    # Thêm nhiều examples...
]

dataset = prepare_instruction_dataset(sample_data)
print(f"\nSample training example:\n{dataset['train'][0]['text']}")
```

```python
# === KIỂM TRA CHẤT LƯỢNG DATA ===
from collections import Counter
import statistics

def analyze_dataset_quality(examples: list[dict]) -> dict:
    """Phân tích chất lượng dataset trước khi train"""

    instruction_lengths = [len(ex['instruction'].split()) for ex in examples]
    output_lengths = [len(ex['output'].split()) for ex in examples]

    # Kiểm tra duplicates
    instructions = [ex['instruction'].strip().lower() for ex in examples]
    instruction_counts = Counter(instructions)
    duplicates = {k: v for k, v in instruction_counts.items() if v > 1}

    report = {
        "total_examples": len(examples),
        "instruction_stats": {
            "mean": statistics.mean(instruction_lengths),
            "median": statistics.median(instruction_lengths),
            "min": min(instruction_lengths),
            "max": max(instruction_lengths),
        },
        "output_stats": {
            "mean": statistics.mean(output_lengths),
            "median": statistics.median(output_lengths),
            "min": min(output_lengths),
            "max": max(output_lengths),
        },
        "duplicate_instructions": len(duplicates),
        "issues": []
    }

    # Cảnh báo
    if report["output_stats"]["mean"] < 10:
        report["issues"].append("⚠️  Output quá ngắn trung bình — có thể thiếu context")

    if report["duplicate_instructions"] > len(examples) * 0.05:
        report["issues"].append(f"⚠️  Nhiều duplicate ({len(duplicates)} unique duplicates)")

    if len(examples) < 100:
        report["issues"].append("⚠️  Dataset nhỏ (<100) — có thể không đủ để fine-tune tốt")

    return report

# Test
report = analyze_dataset_quality(sample_data)
print("Dataset Quality Report:")
for key, value in report.items():
    if key != "issues":
        print(f"  {key}: {value}")
if report["issues"]:
    print("\nIssues:")
    for issue in report["issues"]:
        print(f"  {issue}")
```

### 4. Evaluation Metrics

**WHY:** Không thể cải thiện những gì không đo được. BLEU, ROUGE, perplexity là các metrics chuẩn để so sánh model performance khách quan.

```python
# uv add nltk rouge-score
import math
from collections import Counter
from typing import List

# === PERPLEXITY ===
def calculate_perplexity_simple(model, tokenizer, texts: list[str]) -> float:
    """
    Perplexity = exp(average negative log likelihood)
    Đo model "ngạc nhiên" khi gặp text. Thấp = model hiểu text tốt.
    Baseline GPT-2 trên Wikipedia: ~50, fine-tuned: <20 là tốt
    """
    import torch

    total_loss = 0
    total_tokens = 0

    model.eval()
    with torch.no_grad():
        for text in texts:
            inputs = tokenizer(text, return_tensors="pt", max_length=512, truncation=True)
            input_ids = inputs["input_ids"]

            outputs = model(**inputs, labels=input_ids)
            loss = outputs.loss  # cross-entropy loss

            total_loss += loss.item() * input_ids.shape[1]
            total_tokens += input_ids.shape[1]

    avg_loss = total_loss / total_tokens
    perplexity = math.exp(avg_loss)
    return perplexity

# === BLEU SCORE (tự implement để hiểu cơ chế) ===
def calculate_bleu(reference: str, hypothesis: str, max_n: int = 4) -> float:
    """
    BLEU (Bilingual Evaluation Understudy): đo overlap n-grams.
    Range: 0.0 - 1.0 (1.0 = perfect match).
    Dùng cho: translation, summarization.
    Note: BLEU thấp không nhất thiết nghĩa là model tệ.
    """
    ref_tokens = reference.lower().split()
    hyp_tokens = hypothesis.lower().split()

    if not hyp_tokens:
        return 0.0

    precisions = []

    for n in range(1, max_n + 1):
        # Tạo n-grams
        ref_ngrams = Counter(
            tuple(ref_tokens[i:i+n])
            for i in range(len(ref_tokens) - n + 1)
        )
        hyp_ngrams = Counter(
            tuple(hyp_tokens[i:i+n])
            for i in range(len(hyp_tokens) - n + 1)
        )

        if not hyp_ngrams:
            precisions.append(0)
            continue

        # Clipped precision
        clipped_count = sum(
            min(count, ref_ngrams.get(ngram, 0))
            for ngram, count in hyp_ngrams.items()
        )
        total_count = sum(hyp_ngrams.values())

        if total_count == 0:
            precisions.append(0)
        else:
            precisions.append(clipped_count / total_count)

    # Brevity penalty — phạt khi output ngắn hơn reference
    bp = min(1.0, math.exp(1 - len(ref_tokens) / len(hyp_tokens))) if len(hyp_tokens) > 0 else 0

    # BLEU = BP * geometric mean của precisions
    if all(p == 0 for p in precisions):
        return 0.0

    log_avg = sum(
        math.log(p) if p > 0 else float('-inf')
        for p in precisions
    ) / len(precisions)

    return bp * math.exp(log_avg)

# Test BLEU
ref = "The cat sat on the mat"
hyp1 = "The cat sat on the mat"       # perfect
hyp2 = "A cat is sitting on mat"      # similar
hyp3 = "The dog runs in the park"     # different

print(f"BLEU scores:")
print(f"  Perfect match:  {calculate_bleu(ref, hyp1):.3f}")
print(f"  Similar:        {calculate_bleu(ref, hyp2):.3f}")
print(f"  Different:      {calculate_bleu(ref, hyp3):.3f}")
```

```python
# === ROUGE SCORE ===
from rouge_score import rouge_scorer

def evaluate_with_rouge(
    references: list[str],
    hypotheses: list[str]
) -> dict:
    """
    ROUGE (Recall-Oriented Understudy for Gisting Evaluation):
    - ROUGE-1: unigram overlap
    - ROUGE-2: bigram overlap
    - ROUGE-L: longest common subsequence
    Dùng cho: summarization, text generation.
    """
    scorer = rouge_scorer.RougeScorer(['rouge1', 'rouge2', 'rougeL'], use_stemmer=True)

    results = {"rouge1": [], "rouge2": [], "rougeL": []}

    for ref, hyp in zip(references, hypotheses):
        scores = scorer.score(ref, hyp)
        results["rouge1"].append(scores["rouge1"].fmeasure)
        results["rouge2"].append(scores["rouge2"].fmeasure)
        results["rougeL"].append(scores["rougeL"].fmeasure)

    # Average scores
    import statistics
    avg_results = {
        metric: {
            "mean": statistics.mean(scores),
            "min": min(scores),
            "max": max(scores)
        }
        for metric, scores in results.items()
    }

    return avg_results

# Test ROUGE
references = [
    "Machine learning is a subset of artificial intelligence that learns from data",
    "Python is widely used in data science and machine learning projects"
]

hypotheses = [
    "Machine learning involves learning patterns from data to make predictions",
    "Python programming language is popular for data science applications"
]

rouge_results = evaluate_with_rouge(references, hypotheses)
print("\nROUGE Evaluation:")
for metric, stats in rouge_results.items():
    print(f"  {metric}: mean={stats['mean']:.3f}, min={stats['min']:.3f}, max={stats['max']:.3f}")
```

```python
# === COMPLETE EVALUATION PIPELINE ===
def evaluate_model_comprehensive(
    model_outputs: list[dict],  # [{"input": "...", "output": "...", "expected": "..."}]
) -> dict:
    """
    Đánh giá model với nhiều metrics.
    Trả về comprehensive report.
    """
    from rouge_score import rouge_scorer

    scorer = rouge_scorer.RougeScorer(['rouge1', 'rouge2', 'rougeL'], use_stemmer=True)

    bleu_scores = []
    rouge1_scores = []
    rouge2_scores = []
    rougeL_scores = []
    length_ratios = []

    for item in model_outputs:
        expected = item["expected"]
        actual = item["output"]

        # BLEU
        bleu = calculate_bleu(expected, actual)
        bleu_scores.append(bleu)

        # ROUGE
        rouge = scorer.score(expected, actual)
        rouge1_scores.append(rouge["rouge1"].fmeasure)
        rouge2_scores.append(rouge["rouge2"].fmeasure)
        rougeL_scores.append(rouge["rougeL"].fmeasure)

        # Length ratio (output so với expected)
        exp_len = len(expected.split())
        act_len = len(actual.split())
        length_ratios.append(act_len / exp_len if exp_len > 0 else 0)

    import statistics

    return {
        "num_examples": len(model_outputs),
        "bleu": {
            "mean": statistics.mean(bleu_scores),
            "median": statistics.median(bleu_scores)
        },
        "rouge1_f1": statistics.mean(rouge1_scores),
        "rouge2_f1": statistics.mean(rouge2_scores),
        "rougeL_f1": statistics.mean(rougeL_scores),
        "avg_length_ratio": statistics.mean(length_ratios),
        "interpretation": {
            "bleu": "BLEU > 0.3 là tốt cho generation, > 0.5 là excellent",
            "rouge1": "ROUGE-1 > 0.4 thường được chấp nhận cho summarization",
            "note": "Luôn kết hợp với human evaluation cho kết quả tin cậy"
        }
    }

# Test
sample_outputs = [
    {
        "input": "What is Python?",
        "output": "Python is a programming language used for web development and AI",
        "expected": "Python is a high-level programming language known for its simplicity"
    },
    {
        "input": "Explain list comprehension",
        "output": "List comprehension creates lists concisely: [x for x in range(10)]",
        "expected": "List comprehensions provide a concise way to create lists using a single line"
    }
]

report = evaluate_model_comprehensive(sample_outputs)
print("\nComprehensive Evaluation Report:")
for key, value in report.items():
    if key != "interpretation":
        print(f"  {key}: {value}")
```

## ⚠️ Common Mistakes

| Sai lầm | Hậu quả | Cách fix đúng |
|---------|---------|---------------|
| Fine-tune khi prompt engineering đủ | Lãng phí time/money | Luôn thử prompt engineering trước |
| Dùng toàn bộ dataset không split | Không biết model có overfit không | Luôn tạo train/val/test split |
| Rank LoRA quá cao (r=64+) | Overfitting, tốn VRAM | Bắt đầu r=8, tăng dần nếu cần |
| Learning rate quá cao | Training không hội tụ, model hỏng | LoRA thường 1e-4 đến 3e-4 |
| Không validate data quality | Garbage in, garbage out | Luôn chạy data quality analysis trước |
| Chỉ dùng 1 metric | Đánh giá không toàn diện | Kết hợp BLEU + ROUGE + human eval |
| Forget catastrophic forgetting | Model quên kiến thức gốc | Dùng LoRA thay vì full fine-tune |

## ✅ Best Practices

- **Thử theo thứ tự:** Prompt engineering → Few-shot → RAG → Fine-tuning. Mỗi bước phức tạp hơn bước trước.
- **Dataset quality > quantity:** 500 examples chất lượng cao tốt hơn 5000 examples rác.
- **Validate với test set held-out:** Không bao giờ evaluate trên training data.
- **Save checkpoints thường xuyên:** `save_steps=100`, training crash mất progress.
- **Dùng LoRA rank thấp đầu tiên:** r=4 hay r=8 thường đủ tốt, ít overfit hơn.
- **Monitor training loss và validation loss:** Nếu val_loss tăng mà train_loss giảm → overfitting.
- **Mix data cũ và mới:** Thêm general instruction data để tránh catastrophic forgetting.

## ⚖️ Trade-offs

**Full Fine-tuning vs LoRA vs QLoRA:**

| | Full Fine-tuning | LoRA | QLoRA |
|--|-----------------|------|-------|
| VRAM cần | ~16x model size | ~4x model size | ~2x model size |
| Chất lượng | Tốt nhất | Gần bằng | Gần bằng LoRA |
| Inference speed | Giống gốc | Giống gốc | Chậm hơn 20% |
| Use case | Khi có nhiều GPU | GPU 16-40GB | Consumer GPU (8-16GB) |

**LoRA rank:**
- r=1-4: Rất ít params, nhanh, đủ cho simple tasks
- r=8-16: Balanced, phổ biến nhất
- r=32-64: Nhiều params, risk overfitting, dùng cho complex tasks

## 🚀 Performance Notes

- **Gradient checkpointing:** `model.gradient_checkpointing_enable()` giảm 30-70% VRAM, chậm hơn 20%.
- **Mixed precision (fp16/bf16):** Giảm 50% VRAM, tăng tốc 30-50% trên GPU hiện đại.
- **Flash Attention 2:** Có thể tăng tốc đáng kể cho long sequences, nhưng phụ thuộc model support, dtype `fp16`/`bf16`, GPU/backend và padding pattern.
- **Gradient accumulation:** Simulate large batch size mà không cần nhiều VRAM.
- **DeepSpeed/FSDP:** Cho training trên multi-GPU, không cần với consumer GPU setup.

## 📝 Tóm tắt

- Thứ tự ưu tiên: Prompt Engineering → RAG → Fine-tuning. Đừng nhảy thẳng vào fine-tuning.
- LoRA thường chỉ train một phần rất nhỏ parameters; hiệu quả phụ thuộc data, base model, target modules và eval set.
- QLoRA = LoRA + quantization; có thể đưa một số model 7B vào GPU consumer, nhưng VRAM thực tế phụ thuộc sequence length, batch size, optimizer, checkpointing và backend.
- Data quality quan trọng hơn model architecture hoặc hyperparameters.
- Luôn split data thành train/val/test và evaluate trước khi deploy.
- BLEU và ROUGE là metrics bổ sung, không thay thế được human evaluation.
- Perplexity đo model hiểu ngôn ngữ tốt đến đâu, thấp hơn = tốt hơn.
