from __future__ import annotations

import json
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import torch
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from transformers import AutoModelForSequenceClassification, AutoTokenizer

MODEL_DIR = Path(os.getenv("MODEL_DIR", "artifacts/sentiment_classifier/best_model"))
LABEL_PATH = Path(os.getenv("LABEL_PATH", "artifacts/sentiment_classifier/labels.json"))
MODEL_VERSION = os.getenv("MODEL_VERSION", "sentiment-v1")
MAX_LENGTH = int(os.getenv("MAX_LENGTH", "128"))
MAX_BATCH_SIZE = int(os.getenv("MAX_BATCH_SIZE", "32"))

state: dict[str, Any] = {}


def normalize_text(text: str) -> str:
    return " ".join(str(text).strip().split())


def load_labels(model: AutoModelForSequenceClassification) -> list[str]:
    if LABEL_PATH.exists():
        payload = json.loads(LABEL_PATH.read_text(encoding="utf-8"))
        return list(payload["labels"])
    return [model.config.id2label[i] for i in range(model.config.num_labels)]


def predict_texts(texts: list[str]) -> list[dict[str, Any]]:
    if "model" not in state or "tokenizer" not in state:
        raise HTTPException(status_code=503, detail="Model is not ready")

    start = time.perf_counter()
    normalized = [normalize_text(text) for text in texts]
    tokenizer = state["tokenizer"]
    model = state["model"]
    device = state["device"]
    labels = state["labels"]

    encoded = tokenizer(
        normalized,
        padding=True,
        truncation=True,
        max_length=MAX_LENGTH,
        return_tensors="pt",
    )
    encoded = {key: value.to(device) for key, value in encoded.items()}

    with torch.inference_mode():
        logits = model(**encoded).logits
        probs = torch.softmax(logits, dim=-1).detach().cpu()

    total_latency_ms = (time.perf_counter() - start) * 1000
    per_item_latency_ms = total_latency_ms / max(len(texts), 1)
    token_counts = encoded["attention_mask"].detach().cpu().sum(dim=1).tolist()

    results = []
    for idx, row in enumerate(probs):
        pred_id = int(torch.argmax(row).item())
        results.append(
            {
                "label": labels[pred_id],
                "confidence": round(float(row[pred_id].item()), 6),
                "probabilities": {labels[i]: round(float(row[i].item()), 6) for i in range(len(labels))},
                "input_tokens": int(token_counts[idx]),
                "latency_ms": round(per_item_latency_ms, 3),
                "model_version": MODEL_VERSION,
            }
        )
    return results


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not MODEL_DIR.exists():
        raise RuntimeError(f"MODEL_DIR does not exist: {MODEL_DIR}")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    tokenizer = AutoTokenizer.from_pretrained(str(MODEL_DIR))
    model = AutoModelForSequenceClassification.from_pretrained(str(MODEL_DIR)).to(device)
    model.eval()

    state["device"] = device
    state["tokenizer"] = tokenizer
    state["model"] = model
    state["labels"] = load_labels(model)

    # Warmup catches tokenizer/model load issues before the service receives traffic.
    predict_texts(["warmup"])
    yield
    state.clear()


app = FastAPI(title="Vietnamese Sentiment Classifier", version=MODEL_VERSION, lifespan=lifespan)


class PredictRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


class BatchPredictRequest(BaseModel):
    texts: list[str] = Field(min_length=1, max_length=MAX_BATCH_SIZE)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "model_version": MODEL_VERSION}


@app.get("/ready")
def ready() -> dict[str, Any]:
    return {
        "ready": "model" in state,
        "model_dir": str(MODEL_DIR),
        "device": str(state.get("device", "unknown")),
        "labels": state.get("labels", []),
        "max_length": MAX_LENGTH,
    }


@app.post("/predict")
def predict(req: PredictRequest) -> dict[str, Any]:
    return predict_texts([req.text])[0]


@app.post("/predict-batch")
def predict_batch(req: BatchPredictRequest) -> dict[str, Any]:
    texts = [normalize_text(text) for text in req.texts]
    if any(not text for text in texts):
        raise HTTPException(status_code=422, detail="All texts must be non-empty after normalization")
    if len(texts) > MAX_BATCH_SIZE:
        raise HTTPException(status_code=413, detail=f"Batch size must be <= {MAX_BATCH_SIZE}")
    return {"items": predict_texts(texts), "model_version": MODEL_VERSION}
