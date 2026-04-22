#!/bin/bash
echo "[🚫] Stopping all local GPU services..."

for svc in vllm-omni faster-whisper cosyvoice2; do
    pidfile="services/$svc/service.pid"
    if [ -f "$pidfile" ]; then
        pid=$(cat "$pidfile")
        if kill -0 "$pid" 2>/dev/null; then
            echo "  Stopping $svc (PID $pid)..."
            kill "$pid"
            rm "$pidfile"
        fi
    fi
done

echo "[✅] All local services stopped."
