#!/usr/bin/env python3
"""Wyoming STT Adapter — bridges Wyoming Protocol to faster-whisper HTTP API."""
import os
import asyncio
import io
import wave
import httpx
from wyoming.server import AsyncServer
from wyoming.asr import Transcribe, Transcript
from wyoming.audio import AudioChunk, AudioStop
from wyoming.event import Event

BACKEND_URL = os.getenv("STT_BACKEND_URL", "http://host.docker.internal:10300")
LANGUAGE = os.getenv("STT_LANGUAGE", "zh")

async def main():
    uri = os.getenv("WYOMING_URI", "tcp://0.0.0.0:10310")
    server = AsyncServer.from_uri(uri)
    print(f"Wyoming STT Adapter starting on {uri} -> {BACKEND_URL}")
    await server.run(handler)

async def handler(reader, writer):
    audio_buffer = io.BytesIO()
    
    async for event in reader:
        if AudioChunk.is_type(event.type):
            chunk = AudioChunk.from_event(event)
            audio_buffer.write(chunk.audio)
        elif AudioStop.is_type(event.type):
            # Convert raw audio to WAV
            audio_buffer.seek(0)
            wav_buffer = io.BytesIO()
            with wave.open(wav_buffer, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(16000)
                wf.writeframes(audio_buffer.getvalue())
            
            wav_buffer.seek(0)
            async with httpx.AsyncClient() as client:
                files = {"file": ("audio.wav", wav_buffer.getvalue(), "audio/wav")}
                resp = await client.post(f"{BACKEND_URL}/transcribe", files=files, timeout=30.0)
                result = resp.json()
            
            transcript = Transcript(text=result.get("text", ""))
            await writer.write_event(transcript.event())
            audio_buffer = io.BytesIO()

if __name__ == "__main__":
    asyncio.run(main())
