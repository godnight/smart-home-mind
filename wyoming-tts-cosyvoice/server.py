#!/usr/bin/env python3
"""Wyoming TTS Server using CosyVoice2 (Chinese voice cloning)."""

import argparse
import asyncio

from wyoming.server import AsyncServer

# TODO: Implement CosyVoice2 integration

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--uri", default="tcp://0.0.0.0:10301")
    args = parser.parse_args()
    print(f"TTS server starting on {args.uri}")

if __name__ == "__main__":
    asyncio.run(main())
