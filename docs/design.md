# Smart Home Mind — 详细设计文档

## 1. 设计目标

构建一套**中文优先、本地为主、Home Assistant 原生集成** 的 AI 语音助手方案。

核心理念：
- **Wyoming Protocol** 标准化：与 Home Assistant 官方语音流水线无缝对接
- **GPU 服务宿主机原生运行**：充分利用 4090 显存，避免 Docker 容器内 GPU 调度开销
- **LLM 路由灵活**：支持 Kimi API 云端大脑 + 本地 vLLM 私有部署
- **Docker 运行轻量服务**：适配器、网关等非 GPU 服务用 Docker 一键启动

---

## 2. 现状与已有资产

| 组件 | 状态 | 位置 |
|-------|-------|-------|
| vLLM-Omni (Qwen2.5-Omni-7B) | 环境存在，未运行 | `~/vllm-omni-env` |
| Qwen2.5-Omni-7B 模型 | 已下载 | `/mnt/d/models/Qwen2.5-Omni-7B` |
| faster-whisper | 未安装 | 需安装 |
| CosyVoice2-0.5B | 未安装 | 需安装 |
| ffmpeg | 未安装 | 系统依赖 |
| Home Assistant | 已部署 | 用户现有 |

---

## 3. 系统架构

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         宿主机（Ubuntu WSL + 4090 GPU）                          │
│                                                                                  │
│  ┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐   │
│  │ faster-whisper    │  │  vLLM-Omni       │  │ CosyVoice2      │   │
│  │   (STT Engine)    │  │  (LLM Engine)    │  │   (TTS Engine)    │   │
│  │   Port: 10300     │  │  Port: 8000      │  │   Port: 5000      │   │
│  └─────────────────────┘  └─────────────────────┘  └─────────────────────┘   │
│           │                  │                  │                    │
│           └────────────────┼────────────────┼────────────────┘                    │
│                      │                                                          │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │                    Docker Compose Network (smart-home-mind)                   │   │
│  │                                                                              │   │
│  │  ┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐ │   │
│  │  │ Wyoming STT     │  │  LLM Gateway     │  │ Wyoming TTS     │ │   │
│  │  │   Adapter       │  │                 │  │   Adapter       │ │   │
│  │  │   Port: 10310   │  │   Port: 8080    │  │   Port: 10311   │ │   │
│  │  └─────────────────────┘  └─────────────────────┘  └─────────────────────┘ │   │
│  └──────────────────────────────────────────────────────────────────────────┘   │
│                                                                                  │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │                         Home Assistant (已有部署)                            │   │
│  │    Wyoming Voice ←───────────────────────────────────→    │   │
│  └──────────────────────────────────────────────────────────────────────────┘   │
│                                                                                  │
└──────────────────────────────────────────────────────────────────────────┘
```

### 关键设计决策

1. **GPU 服务宿主机原生运行**：
   - vLLM-Omni、faster-whisper、CosyVoice2 均需要 CUDA
   - Docker 内运行 GPU 服务需要 nvidia-docker 和额外配置
   - 宿主机运行可以更直接地利用现有环境和模型

2. **Docker 内运行轻量服务**：
   - Wyoming 适配器：负载网络代理，无需 GPU
   - LLM Gateway：FastAPI 服务，负载代理

3. **Adapter 层抽象**：
   - Wyoming STT Adapter 将 faster-whisper 的原生 API 转换为 Wyoming Protocol
   - Wyoming TTS Adapter 将 CosyVoice2 的原生 API 转换为 Wyoming Protocol
   - LLM Gateway 将多种 LLM 后端统一为 OpenAI 兼容 API

---

## 4. 数据流

```
1. 用户说话 → Home Assistant Wyoming Voice → Wyoming STT Adapter (TCP 10310)
2. Wyoming STT Adapter → faster-whisper API (HTTP 本地10300) → 返回文本
3. Wyoming STT Adapter → 返回 Transcript 给 HA
4. HA → 将文本发送给 LLM Gateway (HTTP 8080)
5. LLM Gateway → Kimi API / 本地 vLLM (8000) → 返回回复文本
6. HA → 将回复发送给 Wyoming TTS Adapter (TCP 10311)
7. Wyoming TTS Adapter → CosyVoice2 API (HTTP 本地5000) → 返回音频
8. Wyoming TTS Adapter → 返回 AudioChunk 给 HA → 播放
```

---

## 5. 模块设计

### 5.1 Wyoming STT Adapter (`wyoming-stt-adapter/`)

职责：将 faster-whisper 包装为 Wyoming 服务

接口：
- 输入：Wyoming AudioChunk + AudioStop
- 输出：Wyoming Transcript
- 内部调用：`POST http://host.docker.internal:10300/transcribe`

配置：
```env
STT_BACKEND_URL=http://host.docker.internal:10300
STT_LANGUAGE=zh
STT_MODEL=base
```

### 5.2 Wyoming TTS Adapter (`wyoming-tts-adapter/`)

职责：将 CosyVoice2 包装为 Wyoming 服务

接口：
- 输入：Wyoming Synthesize
- 输出：Wyoming AudioChunk + AudioStop
- 内部调用：`POST http://host.docker.internal:5000/inference`

配置：
```env
TTS_BACKEND_URL=http://host.docker.internal:5000
TTS_VOICE=default
TTS_SPEED=1.0
```

### 5.3 LLM Gateway (`llm-gateway/`)

职责：统一 LLM 路由

接口：
- `GET /` — 健康检查
- `POST /v1/chat/completions` — 对接 OpenAI API 格式，支持 streaming

路由逻辑：
- 根据配置的 `LLM_BACKEND` 选择后端
- 支持 Kimi、本地 vLLM、任意 OpenAI 兼容服务
- 可扩展添加更多后端

配置：
```env
LLM_BACKEND=kimi  # 或 vllm
KIMI_BASE_URL=https://api.moonshot.cn/v1
KIMI_API_KEY=xxx
KIMI_MODEL=kimi-latest

VLLM_BASE_URL=http://host.docker.internal:8000/v1
VLLM_API_KEY=empty
VLLM_MODEL=Qwen2.5-Omni-7B
```

### 5.4 本地 GPU 服务管理（新增 `scripts/` 和 `services/`）

职责：管理宿主机上的 GPU 服务启停

文件：
- `scripts/start-services.sh` — 一键启动 faster-whisper + CosyVoice2 + vLLM-Omni
- `scripts/stop-services.sh` — 一键停止
- `services/faster-whisper/` — 启动脚本和配置
- `services/cosyvoice2/` — 启动脚本和配置
- `services/vllm-omni/` — 启动脚本和配置

---

## 6. 部署流程

### 6.1 初始化（一次性）

```bash
# 1. 克隆项目
git clone https://github.com/godnight/smart-home-mind.git
cd smart-home-mind

# 2. 安装本地依赖
sudo apt install ffmpeg
pip install -r requirements-local.txt  # faster-whisper, cosyvoice

# 3. 配置
mkdir -p data/whisper-models data/cosyvoice-models
cp config/example.env config/.env
# 编辑 config/.env

# 4. 启动本地 GPU 服务
./scripts/start-services.sh

# 5. 启动 Docker 服务
docker-compose up -d

# 6. 在 Home Assistant 中配置 Wyoming Voice
#    设置 → 语音助手 → 添加 Wyoming 服务
#    STT: host.docker.internal:10310
#    TTS: host.docker.internal:10311
```

### 6.2 日常启动

```bash
docker-compose up -d
./scripts/start-services.sh
```

---

## 7. Home Assistant 配置

### 7.1 Wyoming Voice 配置

在 HA 中添加两个 Wyoming 服务：
- **STT 服务**：Host: `host.docker.internal`，Port: `10310`
- **TTS 服务**：Host: `host.docker.internal`，Port: `10311`

### 7.2 LLM 对话代理

在 HA 中配置 OpenAI 兼容的对话代理：
- Base URL: `http://host.docker.internal:8080/v1`
- API Key: `dummy`
- Model: `smart-home-mind`

---

## 8. 开发路线图

```
Phase 1: 基础设施
  ├── 安装 ffmpeg
  ├── 安装 faster-whisper 环境
  ├── 安装 CosyVoice2 环境
  └── 验证 vLLM-Omni 启动

Phase 2: 适配器实现
  ├── Wyoming STT Adapter
  ├── Wyoming TTS Adapter
  └── LLM Gateway 完善

Phase 3: 音频调试
  ├── 单模块测试（STT/TTS/Gateway单独验证）
  ├── 整链路测试（HA → STT → LLM → TTS）
  └── 音质优化和延迟优化

Phase 4: 产品化
  ├── 完善 README 和文档
  ├── GitHub Actions CI
  └── 社区推广
```
