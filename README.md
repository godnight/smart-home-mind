# Smart Home Mind

A local-first, LLM-powered voice assistant for Home Assistant, optimized for Chinese.

## 特点

- 🎤 **中文语音优化** — faster-whisper + CosyVoice2 本地运行
- 🤖 **LLM 双引擎** — 支持 Kimi API 云端 + 本地 vLLM 私有部署
- 🏠 **Home Assistant 原生集成** — Wyoming Protocol 标准对接
- 🚀 **GPU 服务宿主机原生** — 充分利用显存，Docker 运行轻量服务

## 架构

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         宿主机（GPU 服务）                              │
│  faster-whisper ──────────────────────────────────────────────────→ │
│       │                      vLLM-Omni                        CosyVoice2         │
│       │                          │                               ↑              │
│       └─────────────────────┼─────────────────────┘                    │
│                                  │                                               │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │                    Docker 容器（轻量服务）                             │   │
│  │  Wyoming STT Adapter ←─────── LLM Gateway ────────→ Wyoming TTS Adapter  │   │
│  └──────────────────────────────────────────────────────────────────────────┘   │
│                                  │                                               │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │                         Home Assistant                                     │   │
│  └──────────────────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────────┘
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

# 4. 启动 Docker 服务
docker-compose up -d

# 5. 在 Home Assistant 中配置 Wyoming Voice
#    STT: host.docker.internal:10310
#    TTS: host.docker.internal:10311
#    LLM: http://host.docker.internal:8080/v1
```

## 模块说明

| 模块 | 路径 | 说明 |
|-----|-------|------|
| Wyoming STT Adapter | `wyoming-stt-adapter/` | faster-whisper 的 Wyoming 协议适配器 |
| Wyoming TTS Adapter | `wyoming-tts-adapter/` | CosyVoice2 的 Wyoming 协议适配器 |
| LLM Gateway | `llm-gateway/` | 统一 LLM 路由网关 |
| 本地服务脚本 | `scripts/`, `services/` | 管理宿主机 GPU 服务的启停脚本 |

## 详细设计

见 [docs/design.md](docs/design.md)

## License

MIT
