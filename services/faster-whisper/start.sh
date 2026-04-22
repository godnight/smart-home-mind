#!/bin/bash
# faster-whisper 服务启动脚本
set -e

ENV_PATH="${SHM_ENV:-$HOME/shm-env}"
MODEL=${WHISPER_MODEL:-base}
PORT=${WHISPER_PORT:-10300}
DEVICE=${WHISPER_DEVICE:-cuda}

cd "$(dirname "$0")"
source "$ENV_PATH/bin/activate"

python3 server.py &
echo $! > service.pid
echo "faster-whisper started on port $PORT (PID $!)"
