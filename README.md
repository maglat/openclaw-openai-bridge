# OpenClaw OpenAI Bridge

Bridge, die OpenClaw als OpenAI-kompatible API verfügbar macht. Ermöglicht die Integration von OpenClaw als LLM in **Open WebUI** und **Home Assistant**.

## ✨ Features

- ✅ **OpenAI-kompatible API** (`/v1/chat/completions`)
- ✅ **Streaming Support** (SSE - Server-Sent Events)
- ✅ **Multimodal** (Bilder-Upload & Analyse)
- ✅ **Session Management** (einfach & sauber)
- ✅ **macOS LaunchAgent** (permanent im Hintergrund)
- ✅ **Home Assistant Integration** (mit `hass_local_openai_llm`)
- ✅ **Open WebUI Integration** (als Custom LLM)
- ✅ **Smart Chunking** (keine gebrochenen Wörter)
- ✅ **Fixed Session IDs** (Context über Anfragen hinweg)

## 📋 Voraussetzungen

- macOS (oder Linux mit systemd)
- Python 3.10+
- OpenClaw mit Gateway (port 18789)
- Open WebUI (optional)
- Home Assistant (optional)

## 🚀 Installation

### 1. Bridge Script herunterladen

```bash
# Bridge Script nach ~/.openclaw/workspace/scripts/ kopieren
mkdir -p ~/.openclaw/workspace/scripts/openclaw-openai-bridge
cp openai-openclaw-bridge-streaming.py ~/.openclaw/workspace/scripts/openclaw-openai-bridge/
```

### 2. Konfiguration anpassen

Öffne `openai-openclaw-bridge-streaming.py` und passe die Configuration an:

```python
CONFIG = {
    "port": 9000,              # Port der Bridge
    "host": "192.168.178.5",   # IP des Mac Mini (lokal!)
    "api_key": "seibot",       # Optional: API Key für Authentifizierung
    "session_prefix": "ha-bridge",  # Session Prefix
    "log_file": "/Users/elonseibot/.openclaw/workspace/logs/openclaw-openai-bridge-streaming.log"
}
```

> ⚠️ **Wichtig:** `host` muss die lokale IP des Mac Mini sein (nicht 127.0.0.1), damit Home Assistant die Bridge erreichen kann!

### 3. LaunchAgent einrichten (macOS)

Die LaunchAgent plist startet die Bridge automatisch beim Boot:

```bash
# LaunchAgent installieren
cp com.openclaw.openai-bridge.plist ~/Library/LaunchAgents/

# LaunchAgent laden und starten
launchctl load ~/Library/LaunchAgents/com.openclaw.openai-bridge.plist
launchctl start com.openclaw.openai-bridge
```

### 4. Status prüfen

```bash
# Ist die Bridge aktiv?
ps aux | grep "openai-openclaw-bridge"

# Logs prüfen
tail -f ~/.openclaw/workspace/logs/openclaw-openai-bridge-streaming.log
```

## 🔧 Integration

### Open WebUI

In Open WebUI Settings → LLM:

```
[ ] Open AI API
✅ Custom API

API Provider: OpenAI
Base URL: http://192.168.178.5:9000/v1
API Key: seibot
Model: seibot
```

**Modell einrichten:**
```
Model Name: OpenClaw
Model ID: seibot
```

### Home Assistant

1. **Custom Integration installieren:**
   ```bash
   # In config/www/ oder via HACS
   # hass_local_openai_llm Integration
   ```

2. **In HA Settings → LLM:**
   ```
   API Base URL: http://192.168.178.5:9000/v1
   API Key: seibot
   Model: seibot
   ```

## 📡 API Endpoints

### POST `/v1/chat/completions`

Chat Completion mit Streaming Support.

**Request:**
```json
{
  "model": "seibot",
  "messages": [
    {"role": "user", "content": "Hallo"}
  ],
  "stream": true
}
```

**Response (Streaming):**
```
data: {"id":"chatcmpl-xxx","object":"chat.completion.chunk","created":1234567890,"model":"seibot","choices":[{"index":0,"delta":{"role":"assistant","content":"Hi"},"finish_reason":null}]}
data: [DONE]
```

### GET `/v1/models`

Listet verfügbare Modelle.

**Response:**
```json
{
  "data": [{
    "id": "seibot",
    "object": "model",
    "owned_by": "openclaw"
  }]
}
```

## 🖼️ Multimodal Support (Bilder)

Open WebUI kann Bilder an die Bridge senden. Die Bridge:

1. **Erkennt Base64-Bilder** im Message-Format
2. **Speichert sie temporär** als `/tmp/openclaw-image-*.jpg`
3. **Übergibt sie an OpenClaw** zur Analyse

**Beispiel:**
```json
{
  "messages": [{
    "role": "user",
    "content": [
      {"type": "text", "text": "Was siehst du?"},
      {
        "type": "image_url",
        "image_url": {
          "url": "data:image/jpeg;base64,/9j/4AAQSkZJRg..."
        }
      }
    ]
  }]
}
```

## 🔐 Sicherheit

- **API Key:** Optional in CONFIG setzen
- **Network:** Bridge lauscht auf spezifischer IP (nicht 0.0.0.0!)
- **Sessions:** Ephemeral pro Request (keine Anhäufung)
- **Temp Files:** Bilder werden in `/tmp/` gespeichert (automatisch cleanup)

## 🧹 Wartung

### Logs prüfen
```bash
tail -f ~/.openclaw/workspace/logs/openclaw-openai-bridge-streaming.log
```

### Bridge neu starten
```bash
launchctl stop com.openclaw.openai-bridge
launchctl start com.openclaw.openai-bridge
```

### Sessions aufräumen
```bash
openclaw sessions cleanup
```

## 🐛 Troubleshooting

### Bridge startet nicht
```bash
# LaunchAgent Status prüfen
launchctl list | grep openai-bridge

# Manuell testen
python3 ~/.openclaw/workspace/scripts/openclaw-openai-bridge/openai-openclaw-bridge-streaming.py
```

### Connection refused
```bash
# Port prüfen
lsof -i :9000

# Firewall prüfen
# macOS: Systemeinstellungen → Netzwerk → Firewall
```

### Open WebUI zeigt "Unable to get response"
```bash
# Bridge Logs prüfen
tail -50 ~/.openclaw/workspace/logs/openclaw-openai-bridge-streaming.log

# Open WebUI DevTools (F12) → Network Tab
```

### BrokenPipeError
```bash
# Bridge neu starten
launchctl restart com.openclaw.openai-bridge
```

## 📁 Projektstruktur

```
openclaw-openai-bridge/
├── openai-openclaw-bridge-streaming.py  # Bridge Script
├── com.openclaw.openai-bridge.plist     # LaunchAgent
├── README.md                            # Diese Datei
└── LICENSE
```

## 🤝 Ähnliche Projekte

- [hass_local_openai_llm](https://github.com/skye-harris/hass_local_openai_llm) - HA Integration
- [Open WebUI](https://github.com/open-webui/open-webui) - Chat UI
- [OpenClaw](https://github.com/openclaw/openclaw) - AI Agent Framework

## 📄 License

MIT License

---

**Built with ❤️ for OpenClaw community**

## 🎯 Verwendungszwecke

- **Open WebUI als Chat UI** mit OpenClaw als LLM
- **Home Assistant Sprachsteuerung** mit OpenClaw
- **Multimodale Interaktion** (Text + Bilder)
- **Persistent Context** über Chat-Sessions hinweg
- **Universelle AI-Integration** für alle OpenAI-API-Clients

## 📦 Package Contents

- **openai-openclaw-bridge-streaming.py** - Haupt-Script (Python 3.10+)
- **com.openclaw.openai-bridge.plist** - macOS LaunchAgent for auto-start
- **README.md** - Setup & Integration Guide

## 🔑 Schlüsselfunktionen

### Streaming (SSE)
Server-Sent Events für Echtzeit-Antworten in Open WebUI & HA

### Smart Chunking
Split at word boundaries → no corrupted words like "Insta nz"

### Multimodal
Upload images → Base64 → vLLM Vision API analysis

### Session Strategy
Ephemeral sessions per request → no context explosion

### Cross-Platform
macOS (LaunchAgent) or Linux (systemd service)
