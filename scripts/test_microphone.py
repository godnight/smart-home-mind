#!/usr/bin/env python3
"""Test wake word detection with local microphone.

Streams microphone audio to the Wyoming Wake Word service via TCP.
Prints detection results in real-time.

Usage:
    source venv/bin/activate
    python scripts/test_microphone.py

Requires:
    pip install sounddevice wyoming
"""
import argparse
import logging
import signal
import sys
import threading

import numpy as np

logging.basicConfig(level=logging.INFO, format="%(message)s")
_LOGGER = logging.getLogger(__name__)

# Wyoming imports
from wyoming.client import AsyncTcpClient
from wyoming.audio import AudioChunk, AudioStart, AudioStop
from wyoming.wake import Detection, NotDetected

SAMPLE_RATE = 16000
CHANNELS = 1
BLOCK_DURATION = 0.08  # 80ms chunks, matching openWakeWord frame size

shutdown_event = threading.Event()


def signal_handler(sig, frame):
    _LOGGER.info("\nShutting down...")
    shutdown_event.set()


async def run_client(host: str, port: int):
    try:
        import sounddevice as sd
    except ImportError:
        _LOGGER.error("sounddevice not installed. Run: pip install sounddevice")
        sys.exit(1)

    # Connect to wake word service
    async with AsyncTcpClient(host, port) as client:
        # Send AudioStart
        await client.write_event(AudioStart(rate=SAMPLE_RATE, width=2, channels=CHANNELS).event())
        _LOGGER.info("Connected to wake word service at %s:%d", host, port)
        _LOGGER.info("Say 'Hey Jarvis' to test. Press Ctrl+C to stop.\n")

        # Audio buffer lock
        buffer_lock = threading.Lock()
        audio_buffer = bytearray()

        def audio_callback(indata, frames, time_info, status):
            if status:
                _LOGGER.warning("Audio status: %s", status)
            # Convert float32 [-1,1] to int16 PCM
            pcm = (indata[:, 0] * 32767).astype(np.int16)
            with buffer_lock:
                audio_buffer.extend(pcm.tobytes())

        # Start microphone stream
        stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype=np.float32,
            blocksize=int(SAMPLE_RATE * BLOCK_DURATION),
            callback=audio_callback,
        )

        with stream:
            while not shutdown_event.is_set():
                # Check for Wyoming responses
                try:
                    event = await client.read_event(timeout=0.05)
                    if event:
                        if Detection.is_type(event.type):
                            det = Detection.from_event(event)
                            _LOGGER.info("🟢 WAKE WORD DETECTED: %s", det.name)
                        elif NotDetected.is_type(event.type):
                            pass  # Too noisy to print every frame
                except Exception:
                    pass

                # Send buffered audio
                with buffer_lock:
                    if len(audio_buffer) >= 1280 * 2:  # 80ms of 16-bit audio
                        chunk_bytes = bytes(audio_buffer[:1280*2])
                        audio_buffer = audio_buffer[1280*2:]
                    else:
                        chunk_bytes = None

                if chunk_bytes:
                    await client.write_event(
                        AudioChunk(rate=SAMPLE_RATE, width=2, channels=CHANNELS, audio=chunk_bytes).event()
                    )

        # Send AudioStop
        await client.write_event(AudioStop().event())


def main():
    parser = argparse.ArgumentParser(description="Test wake word with microphone")
    parser.add_argument("--host", default="localhost", help="Wake word service host")
    parser.add_argument("--port", type=int, default=10400, help="Wake word service port")
    args = parser.parse_args()

    signal.signal(signal.SIGINT, signal_handler)

    import asyncio
    asyncio.run(run_client(args.host, args.port))


if __name__ == "__main__":
    main()
