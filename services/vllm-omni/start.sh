#!/bin/bash
# vLLM-Omni 启动脚本
# 使用已有环境: ~/vllm-omni-env

ENV_PATH="${VLLM_ENV:-$HOME/vllm-omni-env}"
MODEL_PATH="${VLLM_MODEL:-/mnt/d/models/Qwen2.5-Omni-7B}"
PORT=${VLLM_PORT:-8000}

cd "$(dirname "$0")"

source "$ENV_PATH/bin/activate"

nohup python -m vllm.entrypoints.openai.api_server \
    --model "$MODEL_PATH" \
    --port $PORT \
    --trust-remote-code \
    > service.log 2>&1 &

echo $! > service.pid
echo "vLLM-Omni started on port $PORT (PID $!)"
