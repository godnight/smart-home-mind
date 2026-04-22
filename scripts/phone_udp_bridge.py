#!/usr/bin/env python3
"""Bridge: receive UDP audio from phone → forward to Wyoming Wake Word service.

Run this on your PC/WSL:
    python scripts/phone_udp_bridge.py

Then run phone_mic.py on your Android phone (via Termux).
"""
import argparse
import asyncio
import logging
import socket

from wyoming.client import AsyncTcpClient
from wyoming.audio import AudioChunk, AudioStart, AudioStop
from wyoming.wake import Detection

logging.basicConfig(level=logging.INFO, format="%(message)s")
_LOGGER = logging.getLogger(__name__)

SAMPLE_RATE = 16000
WIDTH = 2
CHANNELS = 1
CHUNK_BYTES = 1280 * WIDTH  # 80ms frames


async def bridge(udp_port: int, wyoming_host: str, wyoming_port: int):
    # UDP socket to receive from phone
    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_sock.bind(("0.0.0.0", udp_port))
    udp_sock.setblocking(False)
    _LOGGER.info("UDP listener ready on port %d (waiting for phone...)", udp_port)

    loop = asyncio.get_event_loop()

    async with AsyncTcpClient(wyoming_host, wyoming_port) as client:
        await client.write_event(AudioStart(rate=SAMPLE_RATE, width=WIDTH, channels=CHANNELS).event())
        _LOGGER.info("Connected to wake word service at %s:%d", wyoming_host, wyoming_port)
        _LOGGER.info("Say your wake word when ready.\n")

        while True:
            # Non-blocking UDP receive
            try:
                data = await loop.run_in_executor(None, lambda: udp_sock.recv(CHUNK_BYTES * 2))
            except BlockingIOError:
                await asyncio.sleep(0.01)
                continue

            if data:
                await client.write_event(
                    AudioChunk(rate=SAMPLE_RATE, width=WIDTH, channels=CHANNELS, audio=data).event()
                )

            # Check for detection events (non-blocking)
            try:
                event = await asyncio.wait_for(client.read_event(), timeout=0.001)
                if event and Detection.is_type(event.type):
                    det = Detection.from_event(event)
                    _LOGGER.info("🟢 WAKE WORD DETECTED: %s", det.name)
            except asyncio.TimeoutError:
                pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--udp-port", type=int, default=5000, help="UDP port to listen for phone audio")
    parser.add_argument("--wyoming-host", default="localhost", help="Wake word service host")
    parser.add_argument("--wyoming-port", type=int, default=10400, help="Wake word service port")
    args = parser.parse_args()

    asyncio.run(bridge(args.udp_port, args.wyoming_host, args.wyoming_port))


if __name__ == "__main__":
    main()
