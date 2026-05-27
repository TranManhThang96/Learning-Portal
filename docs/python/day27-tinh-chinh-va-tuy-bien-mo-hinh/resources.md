# Tài Liệu Tham Khảo — Ngày 27

## 📚 Official Docs

- **PEFT Library Docs** — https://huggingface.co/docs/peft — Tài liệu chính thức PEFT, bao gồm LoRA, QLoRA, Prefix Tuning
- **LoRA Paper (arxiv)** — https://arxiv.org/abs/2106.09685 — Paper gốc của LoRA, 12 trang, đọc được ngay cả khi không có background ML
- **QLoRA Paper** — https://arxiv.org/abs/2305.14314 — Paper QLoRA, giải thích cách quantize model 65B về GPU 48GB
- **HuggingFace PEFT Examples** — https://github.com/huggingface/peft/tree/main/examples — Code examples đầy đủ
- **TRL (Training with RL)** — https://huggingface.co/docs/trl — Thư viện SFT, RLHF, DPO training
- **NLTK BLEU Docs** — https://www.nltk.org/api/nltk.translate.bleu_score.html — BLEU implementation trong NLTK
- **rouge-score PyPI** — https://pypi.org/project/rouge-score/ — Google's ROUGE implementation

## 🎥 Video / Courses

- **Fine-tuning LLMs with QLoRA (Tim Dettmers)** — https://www.youtube.com/watch?v=Us5ZFp16PaU — Tác giả QLoRA giải thích trực tiếp
- **HuggingFace Fine-tuning Course** — https://huggingface.co/learn/nlp-course/chapter3 — Chapter 3, training models
- **Practical Fine-tuning Workshop** — https://github.com/brevdev/notebooks — Notebook-based tutorials
- **Sebastian Raschka: LoRA Explained** — https://www.youtube.com/watch?v=dA-NhCtrrVE — Video giải thích LoRA rất rõ ràng

## 📝 Articles / Blog Posts

- **LoRA Explained Simply** — https://huggingface.co/blog/lora — HuggingFace blog, giải thích LoRA với visualizations
- **QLoRA: Efficient Finetuning of Quantized LLMs** — https://huggingface.co/blog/4bit-transformers-bitsandbytes — Hướng dẫn QLoRA thực tế
- **Fine-tuning vs RAG vs Prompt Engineering** — https://www.anyscale.com/blog/fine-tuning-is-for-form-not-facts — Bài viết về khi nào dùng cái nào
- **Alpaca Dataset Format** — https://github.com/tatsu-lab/stanford_alpaca — Format instruction dataset chuẩn
- **A Survey of LLM Evaluation** — https://arxiv.org/abs/2307.03109 — Overview các metrics evaluation

## 🔧 Tools / Libraries

- **peft** — `uv add peft` — Thư viện PEFT của HuggingFace (LoRA, QLoRA...)
- **trl** — `uv add trl` — SFT Trainer, RLHF, DPO (dễ hơn Trainer gốc cho fine-tuning)
- **bitsandbytes** — `uv add bitsandbytes` — 4-bit và 8-bit quantization
- **datasets** — `uv add datasets` — HuggingFace datasets library
- **accelerate** — `uv add accelerate` — Training acceleration, multi-GPU
- **rouge-score** — `uv add rouge-score` — Google ROUGE implementation
- **nltk** — `uv add nltk` — BLEU score và nhiều NLP tools
- **wandb** — `uv add wandb` — Experiment tracking (free tier)
- **Unsloth** — https://github.com/unslothAI/unsloth — Fine-tune LLaMA/Mistral nhanh 2x, memory 60% ít hơn
- **Axolotl** — https://github.com/OpenAccess-AI-Collective/axolotl — Production-grade fine-tuning framework

## 💡 Ghi chú thêm

**Cài đặt nhanh cho ngày 27:**
```bash
uv add transformers peft datasets accelerate bitsandbytes trl
uv add rouge-score nltk torch
```

**Dataset sources miễn phí cho fine-tuning:**
- **Alpaca dataset:** https://huggingface.co/datasets/tatsu-lab/alpaca — 52K instruction examples
- **OpenOrca:** https://huggingface.co/datasets/Open-Orca/OpenOrca — 1M high-quality instructions
- **Dolly:** https://huggingface.co/datasets/databricks/databricks-dolly-15k — 15K human-written instructions
- **ShareGPT:** https://huggingface.co/datasets/anon8231489123/ShareGPT_Vicuna_unfiltered

**Quick LoRA config reference:**
```python
# Cho LLaMA/Mistral style models
LoraConfig(
    r=8,
    lora_alpha=16,
    target_modules=["q_proj", "v_proj", "k_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    lora_dropout=0.05,
    bias="none",
    task_type=TaskType.CAUSAL_LM
)
```

**Hardware requirements ước tính:**
- Dataset analyzer + ROUGE eval: Laptop CPU, < 1 phút với sample nhỏ
- GPT-2 LoRA smoke test (`max_steps=5-10`, batch size 1): Laptop CPU có thể chạy nhưng thời gian dao động mạnh; chỉ dùng để kiểm tra wiring
- Fine-tune GPT-2 (124M) nghiêm túc: Laptop CPU có thể mất hàng chục phút hoặc hơn, không phải yêu cầu bắt buộc
- Fine-tune model 3B với LoRA: thường cần GPU 8GB+ và khoảng vài giờ cho dataset nhỏ; batch size/context dài có thể làm OOM
- Fine-tune model 7B với QLoRA: thường cần GPU 12-24GB để thoải mái hơn; GPU 8GB chỉ nên xem là thử nghiệm rất chặt config
- Fine-tune model 70B với QLoRA: cần GPU lớn/multi-GPU và kinh nghiệm hạ tầng; không thuộc phạm vi buổi 2 giờ

**Thuê GPU / notebook:**
- **Lambda Labs:** https://lambdalabs.com — GPU cloud, xem pricing hiện hành trước khi chạy job dài
- **Vast.ai:** https://vast.ai — Community GPUs, rẻ hơn nhưng độ ổn định/pháp lý/availability khác nhau
- **Google Colab:** https://colab.research.google.com — phù hợp demo notebook; quota/GPU type thay đổi theo tài khoản và thời điểm
- **Runpod:** https://runpod.io — GPU pods/serverless; luôn đặt spending limit và auto-stop
