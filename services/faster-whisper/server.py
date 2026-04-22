#!/usr/bin/env python3
"""faster-whisper HTTP API server."""
import os
import io
import uvicorn
from fastapi import FastAPI, UploadFile, File
from faster_whisper import WhisperModel

app = FastAPI()

model_name = os.getenv("WHISPER_MODEL", "base")
device = os.getenv("WHISPER_DEVICE", "cuda")
print(f"Loading faster-whisper model: {model_name} on {device}")
model = WhisperModel(model_name, device=device, compute_type="float16")
print("Model loaded.")

@app.post("/transcribe")
async def transcribe(file: UploadFile = File(...)):
    content = await file.read()
    segments, info = model.transcribe(io.BytesIO(content), language="zh", beam_size=5)
    text = "".join([seg.text for seg in segments])
    return {"text": text, "language": info.language, "probability": info.language_probability}

@app.get("/health")
def health():
    return {"status": "ok"}

if __name__ == "__main__":
    port = int(os.getenv("WHISPER_PORT", "10300"))
    uvicorn.run(app, host="0.0.0.0", port=port)
