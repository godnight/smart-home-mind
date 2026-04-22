#!/usr/bin/env python3
"""Wyoming STT Server using faster-whisper (Chinese optimized)."""

import argparse
import asyncio

from wyoming.server import AsyncServer

# TODO: Implement faster-whisper integration

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--uri", default="tcp://0.0.0.0:10300")
    args = parser.parse_args()
    print(f"STT server starting on {args.uri}")

if __name__ == "__main__":
    asyncio.run(main())
