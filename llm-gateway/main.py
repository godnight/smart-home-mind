#!/usr/bin/env python3
"""LLM Gateway: unified router for Kimi / local vLLM / OpenAI-compatible APIs."""
import os
import json
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
import httpx

app = FastAPI(title="Smart Home Mind - LLM Gateway")

# Backend config
BACKEND = os.getenv("LLM_BACKEND", "kimi")

CONFIG = {
    "kimi": {
        "base_url": os.getenv("KIMI_BASE_URL", "https://api.moonshot.cn/v1"),
        "api_key": os.getenv("KIMI_API_KEY", ""),
        "model": os.getenv("KIMI_MODEL", "kimi-latest"),
    },
    "vllm": {
        "base_url": os.getenv("VLLM_BASE_URL", "http://host.docker.internal:8000/v1"),
        "api_key": os.getenv("VLLM_API_KEY", "empty"),
        "model": os.getenv("VLLM_MODEL", "Qwen2.5-Omni-7B"),
    },
}

@app.get("/")
def root():
    return {"status": "ok", "gateway": "smart-home-mind", "backend": BACKEND}

@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    body = await request.json()
    cfg = CONFIG[BACKEND]
    
    # Override model if specified in request, otherwise use config
    payload = {**body, "model": body.get("model", cfg["model"])}
    
    headers = {
        "Authorization": f"Bearer {cfg['api_key']}",
        "Content-Type": "application/json",
    }
    
    async with httpx.AsyncClient() as client:
        if body.get("stream", False):
            async def stream():
                async with client.stream(
                    "POST",
                    f"{cfg['base_url']}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=120.0,
                ) as resp:
                    async for line in resp.aiter_lines():
                        if line:
                            yield line + "\n"
            return StreamingResponse(stream(), media_type="text/event-stream")
        else:
            resp = await client.post(
                f"{cfg['base_url']}/chat/completions",
                headers=headers,
                json=payload,
                timeout=120.0,
            )
            return resp.json()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
