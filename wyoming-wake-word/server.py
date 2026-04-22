#!/usr/bin/env python3
"""Wyoming Wake Word Adapter — openWakeWord detection service for Home Assistant.

Receives raw audio via Wyoming Protocol, runs real-time openWakeWord inference,
and emits Detection / NotDetected events.

Environment variables:
    WAKE_WORD_MODEL      Path to .tflite model (default: /models/hey_jarvis.tflite)
    WAKE_WORD_THRESHOLD  Activation threshold 0-1 (default: 0.5)
    WAKE_WORD_COOLDOWN   Seconds between triggers (default: 2.0)
    WYOMING_URI          Bind address (default: tcp://0.0.0.0:10400)
"""
import os
import asyncio
import logging
from pathlib import Path
from collections import deque

import numpy as np
from wyoming.server import AsyncServer
from wyoming.wake import Detect, Detection, NotDetected
from wyoming.audio import AudioChunk, AudioStart, AudioStop

_LOGGER = logging.getLogger(__name__)

SAMPLE_RATE = 16000
FRAME_MS = 80                          # openWakeWord default inference window
FRAME_SAMPLES = int(SAMPLE_RATE * FRAME_MS / 1000)  # 1280 samples
BYTES_PER_SAMPLE = 2                   # 16-bit PCM

try:
    from openwakeword.model import Model
except ImportError as exc:
    _LOGGER.error("openwakeword is required: pip install openwakeword")
    raise


class WakeWordHandler:
    """Handles one Wyoming client connection."""

    def __init__(self, model_path: str, threshold: float = 0.5, cooldown: float = 2.0):
        self.model = Model(wakeword_model_paths=[str(model_path)])
        self.model_name = Path(model_path).stem
        self.threshold = threshold
        self.cooldown = cooldown
        self.last_trigger = 0.0

        # Rolling audio buffer (bytes)
        self._buffer = bytearray()

        _LOGGER.info(
            "Loaded model=%s threshold=%.2f cooldown=%.1fs",
            self.model_name, threshold, cooldown,
        )

    def _process_frame(self, pcm_bytes: bytes) -> float:
        """Run inference on one 80 ms frame. Returns max score."""
        pcm = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        predictions = self.model.predict(pcm)

        # predictions is Dict[str, float]
        max_score = 0.0
        for key, score in predictions.items():
            if isinstance(score, (int, float)):
                max_score = max(max_score, float(score))
        return max_score

    async def handle(self, reader, writer):
        _LOGGER.info("Client connected")
        self._buffer.clear()

        try:
            async for event in reader:
                if AudioChunk.is_type(event.type):
                    chunk = AudioChunk.from_event(event)
                    self._buffer.extend(chunk.audio)

                    # Consume complete 80 ms frames
                    frame_bytes = FRAME_SAMPLES * BYTES_PER_SAMPLE
                    while len(self._buffer) >= frame_bytes:
                        frame = bytes(self._buffer[:frame_bytes])
                        self._buffer = self._buffer[frame_bytes:]

                        score = self._process_frame(frame)
                        now = asyncio.get_event_loop().time()

                        if score > self.threshold:
                            if (now - self.last_trigger) > self.cooldown:
                                _LOGGER.info(
                                    "Wake word '%s' detected (score=%.3f)",
                                    self.model_name, score,
                                )
                                await writer.write_event(
                                    Detection(name=self.model_name).event()
                                )
                                self.last_trigger = now
                            else:
                                _LOGGER.debug("Cooldown active (score=%.3f)", score)
                        else:
                            await writer.write_event(NotDetected().event())

                elif AudioStart.is_type(event.type):
                    _LOGGER.debug("Audio started")
                    self._buffer.clear()
                    # Reset openWakeWord internal state if supported
                    if hasattr(self.model, "reset"):
                        self.model.reset()

                elif AudioStop.is_type(event.type):
                    _LOGGER.debug("Audio stopped")
                    break

                elif Detect.is_type(event.type):
                    detect = Detect.from_event(event)
                    _LOGGER.info("Detect command: %s", detect.names)
                    self._buffer.clear()
                    if hasattr(self.model, "reset"):
                        self.model.reset()

        except Exception:
            _LOGGER.exception("Handler error")
        finally:
            _LOGGER.info("Client disconnected")


async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )

    model_path = Path(os.getenv("WAKE_WORD_MODEL", "/models/hey_jarvis.tflite"))
    threshold = float(os.getenv("WAKE_WORD_THRESHOLD", "0.5"))
    cooldown = float(os.getenv("WAKE_WORD_COOLDOWN", "2.0"))
    uri = os.getenv("WYOMING_URI", "tcp://0.0.0.0:10400")

    if not model_path.exists():
        _LOGGER.error("Model not found: %s", model_path)
        _LOGGER.error(
            "Place a .tflite model in ./models/ or set WAKE_WORD_MODEL env var.\n"
            "Quick test: download a pre-trained model from\n"
            "  https://github.com/dscripka/openWakeWord/tree/main/models"
        )
        return

    server = AsyncServer.from_uri(uri)
    handler = WakeWordHandler(model_path, threshold, cooldown)

    _LOGGER.info("Wyoming Wake Word listening on %s", uri)
    await server.run(handler.handle)


if __name__ == "__main__":
    asyncio.run(main())
