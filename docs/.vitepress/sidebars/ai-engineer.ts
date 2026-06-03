import type { DefaultTheme } from "vitepress";

const aiDay = (
  text: string,
  slug: string,
): DefaultTheme.SidebarItem => ({
  text,
  collapsed: true,
  items: [
    { text: "Lession", link: `/ai-engineer/lessions/${slug}/lession` },
    { text: "Document", link: `/ai-engineer/lessions/${slug}/document` },
    { text: "Exercise", link: `/ai-engineer/lessions/${slug}/exercise` },
  ],
});

export const aiEngineerSidebar: DefaultTheme.SidebarItem[] = [
  {
    text: "AI Engineer 50 Days",
    items: [
      { text: "Overview", link: "/ai-engineer/" },
    ],
  },
  {
    text: "Phase 1: ML Foundation (Day 1-8)",
    collapsed: true,
    items: [
      aiDay("Day 01 - AI Mindset", "day-01-ai-mindset-cho-senior-se"),
      aiDay("Day 02 - Math đủ dùng", "day-02-math-du-dung-cho-ml"),
      aiDay("Day 03 - ML Fundamentals", "day-03-ml-fundamentals"),
      aiDay("Day 04 - Python ML Stack", "day-04-python-ml-stack"),
      aiDay("Day 05 - Feature Engineering", "day-05-feature-engineering"),
      aiDay("Day 06 - Model Evaluation Metrics", "day-06-model-evaluation-metrics"),
      aiDay("Day 07 - Error Analysis & Data Leakage", "day-07-error-analysis-data-leakage-threshold-tuning"),
      aiDay("Day 08 - Customer Churn ML Pipeline", "day-08-customer-churn-ml-pipeline"),
    ],
  },
  {
    text: "Phase 2: Deep Learning, NLP, Transformer (Day 9-16)",
    collapsed: true,
    items: [
      aiDay("Day 09 - Neural Network từ Zero", "day-09-neural-network-tu-zero"),
      aiDay("Day 10 - PyTorch Fundamentals", "day-10-pytorch-fundamentals"),
      aiDay("Day 11 - Training Loop & Optimizer", "day-11-training-loop-optimizer-scheduler"),
      aiDay("Day 12 - NLP & Tokenizer", "day-12-nlp-fundamentals-tokenizer"),
      aiDay("Day 13 - Attention Mechanism", "day-13-attention-mechanism"),
      aiDay("Day 14 - Transformer Architecture", "day-14-transformer-architecture"),
      aiDay("Day 15 - HuggingFace Ecosystem", "day-15-huggingface-ecosystem"),
      aiDay("Day 16 - Fine-tune BERT Classifier", "day-16-fine-tune-phobert-bert-classifier"),
    ],
  },
  {
    text: "Phase 3: LLM Application Engineering (Day 17-24)",
    collapsed: true,
    items: [
      aiDay("Day 17 - LLM Fundamentals", "day-17-llm-fundamentals"),
      aiDay("Day 18 - Prompt Engineering", "day-18-prompt-engineering-thuc-chien"),
      aiDay("Day 19 - Structured Output & Function Calling", "day-19-structured-output-function-calling"),
      aiDay("Day 20 - LLM App Architecture", "day-20-llm-app-architecture-production"),
      aiDay("Day 21 - SDK Comparison", "day-21-raw-sdk-langchain-llamaindex-langgraph"),
      aiDay("Day 22 - Agent Patterns với LangGraph", "day-22-agent-patterns-voi-langgraph"),
      aiDay("Day 23 - Security Basics", "day-23-security-basics-cho-llm-app"),
      aiDay("Day 24 - AI Assistant Tool Calling", "day-24-ai-assistant-tool-calling-memory"),
    ],
  },
  {
    text: "Phase 4: Fine-tuning & Local LLM (Day 25-30)",
    collapsed: true,
    items: [
      aiDay("Day 25 - Fine-tune vs RAG", "day-25-khi-nao-fine-tune-khi-nao-dung-rag"),
      aiDay("Day 26 - Dataset Preparation", "day-26-dataset-preparation-instruction-tuning"),
      aiDay("Day 27 - LoRA/QLoRA Hands-on", "day-27-lora-qlora-hands-on"),
      aiDay("Day 28 - Evaluation Fine-tune", "day-28-evaluation-truoc-sau-fine-tune"),
      aiDay("Day 29 - Local LLM", "day-29-local-llm-ollama-llama-cpp-vllm"),
      aiDay("Day 30 - Quantization & Deploy", "day-30-quantization-deploy-local-model-api"),
    ],
  },
  {
    text: "Phase 5: Production RAG (Day 31-40)",
    collapsed: true,
    items: [
      aiDay("Day 31 - RAG Architecture", "day-31-rag-architecture"),
      aiDay("Day 32 - Embedding Models", "day-32-embedding-models-benchmark-tieng-viet"),
      aiDay("Day 33 - Vector DB", "day-33-vector-db"),
      aiDay("Day 34 - Chunking Strategies", "day-34-chunking-strategies"),
      aiDay("Day 35 - Metadata & Citation", "day-35-metadata-citation-permission-aware-rag"),
      aiDay("Day 36 - Hybrid Search", "day-36-hybrid-search-dense-sparse-bm25"),
      aiDay("Day 37 - Reranking", "day-37-reranking"),
      aiDay("Day 38 - Advanced RAG Patterns", "day-38-advanced-rag-patterns"),
      aiDay("Day 39 - RAG Evaluation", "day-39-rag-evaluation"),
      aiDay("Day 40 - Production RAG System", "day-40-mini-project-production-rag-system"),
    ],
  },
  {
    text: "Phase 6: MLOps & Production AI (Day 41-47)",
    collapsed: true,
    items: [
      aiDay("Day 41 - MLflow", "day-41-mlflow-experiment-tracking-model-registry"),
      aiDay("Day 42 - Model Serving", "day-42-model-serving"),
      aiDay("Day 43 - Docker/K8s/GPU", "day-43-docker-k8s-gpu-serving-ai-workload"),
      aiDay("Day 44 - Observability", "day-44-observability-cho-llm-app"),
      aiDay("Day 45 - Cost Optimization", "day-45-cost-optimization"),
      aiDay("Day 46 - Guardrails", "day-46-guardrails"),
      aiDay("Day 47 - LLM Testing & CI/CD", "day-47-llm-testing-golden-set-cicd-prompt-rag"),
    ],
  },
  {
    text: "Phase 7: Capstone & Portfolio (Day 48-50)",
    collapsed: true,
    items: [
      aiDay("Day 48 - Architecture Review + API", "day-48-capstone-architecture-review-backend-api"),
      aiDay("Day 49 - UI, Monitoring, Eval Report", "day-49-ui-monitoring-evaluation-report"),
      aiDay("Day 50 - README, Demo, CV", "day-50-readme-demo-blog-cv-linkedin"),
    ],
  },
];
