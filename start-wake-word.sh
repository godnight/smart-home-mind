#!/bin/bash
# Start Wyoming Wake Word service (local Python, no Docker)

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

# Activate virtualenv
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi
source venv/bin/activate

# Install deps if missing
python -c "import openwakeword" 2>/dev/null || {
    echo "Installing dependencies..."
    pip install -q wyoming numpy onnxruntime openwakeword
}

# Download model if missing
MODEL_FILE="models/hey_jarvis.onnx"
if [ ! -f "$MODEL_FILE" ]; then
    echo "Downloading wake word model..."
    python scripts/train_wake_word.py download --model hey_jarvis
fi

# Start service
export WAKE_WORD_MODEL="$MODEL_FILE"
export WAKE_WORD_THRESHOLD=0.5
export WAKE_WORD_COOLDOWN=2.0
export WYOMING_URI=tcp://0.0.0.0:10400

echo "Starting Wyoming Wake Word on $WYOMING_URI..."
exec python wyoming-wake-word/server.py
