# Smart Home Mind

A local-first, LLM-powered voice assistant for Home Assistant, optimized for Chinese.

## 特点

- 🎤 **中文语音优化** — faster-whisper + CosyVoice2 本地运行
- 👂 **语音唤醒** — openWakeWord 支持自定义唤醒词，Wyoming 协议原生集成
- 🤖 **LLM 双引擎** — 支持 Kimi API 云端 + 本地 vLLM 私有部署
- 🏠 **Home Assistant 原生集成** — Wyoming Protocol 标准对接
- 🚀 **GPU 服务宿主机原生** — 充分利用显存，Docker 运行轻量服务

## 架构

```
┌──────────────────────────────────────────────────────────────────────────────────────────────┐
│                         宿主机（GPU 服务）                              │
│  faster-whisper ───────────────────────────────────────────→ │
│       │                      vLLM-Omni                        CosyVoice2         │
│       │                          │                               ↑              │
│       └──────────────────────────────────────────────────────────────────────────────────────────────┘
│                                  │                                               │
│  ┌──────────────────────────────────────────────────────────────────────────────────────────────┐   │
│  │                    Docker 容器（轻量服务）                             │   │
│  │  Wyoming STT Adapter ←────── LLM Gateway ───────→ Wyoming TTS Adapter  │   │
│  │       ↑                                                    ↑            │   │
│  │  Wyoming Wake Word                                       │            │   │
│  └──────────────────────────────────────────────────────────────────────────────────────────────┘   │
│                                  │                                               │
│  ┌──────────────────────────────────────────────────────────────────────────────────────────────┐   │
│  │                         Home Assistant                                     │   │
│  └──────────────────────────────────────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────────────────────────────┘
```

## 快速开始

```bash
# 1. 安装依赖
sudo apt install ffmpeg
pip install -r requirements-local.txt

# 2. 配置
cp config/example.env config/.env
# 编辑 config/.env 填入 API 密钥

# 3. 启动本地 GPU 服务
./scripts/start-services.sh

# 4. 下载预训练唤醒词模型（快速测试）
python scripts/train_wake_word.py download --model hey_jarvis

# 5. 启动 Docker 服务（包含唤醒词、STT、TTS、LLM）
docker-compose up -d

# 6. 在 Home Assistant 中配置 Wyoming Voice
#    STT:      host.docker.internal:10310
#    TTS:      host.docker.internal:10311
#    WakeWord: host.docker.internal:10400
#    LLM:      http://host.docker.internal:8080/v1
```

## 模块说明

| 模块 | 路径 | 说明 |
|-----|-------|------|
| Wyoming Wake Word | `wyoming-wake-word/` | openWakeWord 唤醒词检测服务 |
| Wyoming STT Adapter | `wyoming-stt-adapter/` | faster-whisper 的 Wyoming 协议适配器 |
| Wyoming TTS Adapter | `wyoming-tts-adapter/` | CosyVoice2 的 Wyoming 协议适配器 |
| LLM Gateway | `llm-gateway/` | 统一 LLM 路由网关 |
| 本地服务脚本 | `scripts/`, `services/` | 管理宿主机 GPU 服务的启停脚本 |

## 训练自定义唤醒词

```bash
# 1. 准备正样本
mkdir -p models/wake-words/nihao_guanjia/positive
mkdir -p models/wake-words/nihao_guanjia/negative

# 2. 录制 20-50 条唤醒词（如"你好管家"），每条 1-3 秒，16kHz 单声道 WAV，放入 positive/
# 3. 准备负样本（环境音、对话等非唤醒词音频），放入 negative/

# 4. 训练
python scripts/train_wake_word.py train \
    --name nihao_guanjia \
    --positive-dir models/wake-words/nihao_guanjia/positive \
    --negative-dir models/wake-words/nihao_guanjia/negative \
    --output models/nihao_guanjia.onnx

# 5. 修改 docker-compose.yml 中的 WAKE_WORD_MODEL 为 /models/nihao_guanjia.onnx，重启服务
docker-compose up -d --build wyoming-wake-word
```

## 详细设计

见 [docs/design.md](docs/design.md)

## License

MIT
