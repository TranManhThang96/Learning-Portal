from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException

from .schemas import ChatRequest, ChatResponse
from .service import ConversationService

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")

app = FastAPI(title="Day 24 Support AI Assistant", version="0.1.0")
service = ConversationService()


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    try:
        return service.chat(request)
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
