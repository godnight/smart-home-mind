#!/usr/bin/env python3
"""Capture phone microphone and send audio to PC via UDP.

Run this on your Android phone via Termux:
    pkg install python portaudio
    pip install pyaudio
    python phone_mic.py --server 192.168.x.x:5000

Find your PC's IP (same Wi-Fi network):
    # On PC/WSL:
    ip addr | grep inet
"""
import argparse
import socket
import sys

try:
    import pyaudio
except ImportError:
    print("pyaudio not installed. Run: pip install pyaudio")
    sys.exit(1)

SAMPLE_RATE = 16000
CHANNELS = 1
FORMAT = pyaudio.paInt16
CHUNK = 1280  # 80ms @ 16kHz mono 16bit


def main():
    parser = argparse.ArgumentParser(description="Stream phone mic to PC via UDP")
    parser.add_argument("--server", required=True, help="PC IP:port, e.g. 192.168.1.5:5000")
    args = parser.parse_args()

    host, port_str = args.server.rsplit(":", 1)
    port = int(port_str)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    p = pyaudio.PyAudio()
    stream = p.open(
        format=FORMAT,
        channels=CHANNELS,
        rate=SAMPLE_RATE,
        input=True,
        frames_per_buffer=CHUNK,
    )

    print(f"Streaming microphone to {host}:{port}...")
    print("Press Ctrl+C to stop.\n")

    try:
        while True:
            data = stream.read(CHUNK, exception_on_overflow=False)
            sock.sendto(data, (host, port))
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        stream.stop_stream()
        stream.close()
        p.terminate()
        sock.close()


if __name__ == "__main__":
    main()
