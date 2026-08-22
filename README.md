# SychiK — Home Assistant add-ons

Two HA add-ons for the «Сычик» voice assistant: KWS (wake word «Сычик»)
and Speaker ID (resemblyzer 256-dim embeddings).

## Add-ons

| Add-on | What it does | Port |
|--------|--------------|------|
| **SychiK KWS** | Wake word «Сычик» (sherpa-onnx, Russian) | 10400 (Wyoming), 10401 (REST) |
| **SychiK Speaker ID** | Speaker identification (resemblyzer) | 8000 |

## Install in Home Assistant

**Add-on Store → ⋮ → Repositories** → add:
```
https://github.com/monkeleventh/sychik-addons
```
(для приватного — вставь токен: `https://ghp_ТОКЕН@github.com/monkeleventh/sychik-addons`)

После Refresh появятся два add-on'а в секции "SychiK". Установи оба.

## CI

`docker/build-push-action@v5` собирает каждый add-on × каждую архитектуру
и пушит в `ghcr.io/monkeleventh/<addon>:<arch>`.
