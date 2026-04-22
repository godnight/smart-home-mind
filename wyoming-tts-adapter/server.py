#!/usr/bin/env python3
"""Wyoming TTS Adapter — bridges Wyoming Protocol to CosyVoice2 HTTP API."""
import os
import asyncio
import io
import wave
import httpx
from wyoming.server import AsyncServer
from wyoming.tts import Synthesize
from wyoming.audio import AudioChunk, AudioStart, AudioStop

BACKEND_URL = os.getenv("TTS_BACKEND_URL", "http://host.docker.internal:5000")
VOICE = os.getenv("TTS_VOICE", "default")

async def main():
    uri = os.getenv("WYOMING_URI", "tcp://0.0.0.0:10311")
    server = AsyncServer.from_uri(uri)
    print(f"Wyoming TTS Adapter starting on {uri} -> {BACKEND_URL}")
    await server.run(handler)

async def handler(reader, writer):
    async for event in reader:
        if Synthesize.is_type(event.type):
            synth = Synthesize.from_event(event)
            text = synth.text
            
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{BACKEND_URL}/inference",
                    json={"text": text, "voice": VOICE},
                    timeout=60.0
                )
                audio_bytes = resp.content
            
            # Send audio back in chunks
            await writer.write_event(AudioStart(rate=22050, width=2, channels=1).event())
            chunk_size = 1024 * 4
            for i in range(0, len(audio_bytes), chunk_size):
                chunk = audio_bytes[i:i+chunk_size]
                await writer.write_event(AudioChunk(audio=chunk).event())
            await writer.write_event(AudioStop().event())

if __name__ == "__main__":
    asyncio.run(main())
