#!/bin/bash
# faster-whisper 服务启动脚本
# 需要先安装: pip install faster-whisper

MODEL=${WHISPER_MODEL:-base}
PORT=${WHISPER_PORT:-10300}
DEVICE=${WHISPER_DEVICE:-cuda}

cd "$(dirname "$0")"

python3 -c "
from faster_whisper import WhisperModel
import uvicorn
from fastapi import FastAPI, UploadFile, File
import io

app = FastAPI()
model = WhisperModel('$MODEL', device='$DEVICE', compute_type='float16')

@app.post('/transcribe')
async def transcribe(file: UploadFile = File(...)):
    content = await file.read()
    segments, info = model.transcribe(io.BytesIO(content), language='zh', beam_size=5)
    text = ''.join([seg.text for seg in segments])
    return {'text': text, 'language': info.language}

if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=$PORT)
" > server.py

nohup python3 server.py > service.log 2>&1 &
echo $! > service.pid
echo "faster-whisper started on port $PORT (PID $!)"
