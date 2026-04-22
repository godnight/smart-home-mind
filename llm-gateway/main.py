#!/usr/bin/env python3
"""LLM Gateway: unified router for Kimi / local vLLM / OpenAI-compatible APIs."""

import os
from fastapi import FastAPI
import httpx

app = FastAPI(title="Smart Home Mind - LLM Gateway")

LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.moonshot.cn/v1")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "kimi-latest")

@app.get("/")
def root():
    return {"status": "ok", "gateway": "smart-home-mind"}

@app.post("/v1/chat/completions")
async def chat_completions(request: dict):
    """Proxy chat completions to configured LLM backend."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{LLM_BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {LLM_API_KEY}"},
            json={**request, "model": LLM_MODEL},
            timeout=60.0,
        )
        return response.json()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
