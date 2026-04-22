#!/bin/bash
set -e

echo "[⚡] Starting Smart Home Mind local GPU services..."

# 启动 vLLM-Omni
if [ -f services/vllm-omni/start.sh ]; then
    echo "[🚀] Starting vLLM-Omni..."
    bash services/vllm-omni/start.sh
fi

# 启动 faster-whisper
if [ -f services/faster-whisper/start.sh ]; then
    echo "[🎤] Starting faster-whisper..."
    bash services/faster-whisper/start.sh
fi

# 启动 CosyVoice2
if [ -f services/cosyvoice2/start.sh ]; then
    echo "[🗣️] Starting CosyVoice2..."
    bash services/cosyvoice2/start.sh
fi

echo "[✅] All local services started."
echo "Now run: docker-compose up -d"
