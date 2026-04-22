# Smart Home Mind

A local-first, LLM-powered voice assistant for Home Assistant, optimized for Chinese.

## Architecture

```
[Microphone] → [Wyoming STT: faster-whisper] → [LLM Gateway] → [Wyoming TTS: CosyVoice2] → [Speaker]
                                    ↓
                          [Home Assistant]
```

## Quick Start

```bash
cp config/example.env config/.env
# Edit config/.env with your API keys
docker-compose up -d
```

## Modules

- `wyoming-stt-whisper` — Chinese-optimized STT server
- `wyoming-tts-cosyvoice` — Chinese TTS with voice cloning
- `llm-gateway` — Unified LLM router (Kimi / local vLLM / OpenAI-compatible)

## License

MIT
