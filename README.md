# OpenClaw OpenAI Bridge

Bridge, die OpenClaw als OpenAI-kompatible API verfügbar macht. Ermöglicht die Integration von OpenClaw als LLM in **Open WebUI**, **Home Assistant** oder jeden anderen OpenAI-API-Client.

## ✨ Features

- ✅ **OpenAI-kompatible API** (`/v1/chat/completions`)
- ✅ **Streaming Support** (SSE - Server-Sent Events)
- ✅ **Multimodal** (Bilder-Upload & Analyse)
- ✅ **Smart Chunking** (keine gebrochenen Wörter)
- ✅ **Ephemeral Sessions** (keine Context-Akkumulation)
- ✅ **macOS LaunchAgent / Linux systemd** (permanent)
- ✅ **Home Assistant Integration** (mit `hass_local_openai_llm`)
- ✅ **Open WebUI Integration** (als Custom LLM)

## 📋 Voraussetzungen

- macOS (12+) oder Linux mit systemd
- Python 3.10+
- OpenClaw mit Gateway (port 18789)
- Open WebUI oder Home Assistant (optional)

## 🚀 Installation

### 1. Bridge Script herunterladen

```bash
# Repository klonen
git clone https://github.com/maglat/openclaw-openai-bridge.git
cd openclaw-openai-bridge
```

### 2. Konfiguration anpassen

Öffne `openai-openclaw-bridge-streaming.py` und passe die Configuration an:

```python
CONFIG = {
    "port": 9000,                    # Port der Bridge
    "host": "192.168.1.XXX",         # IP des Mac Mini (lokal!)
    "log_file": "/path/to/openclaw-openai-bridge-streaming.log",
    "api_key": None,                 # Optional: API Key für Auth
    "session_prefix": "openclaw",     # Session Prefix
    "timeout": 120,                  # Timeout in Sekunden
}
```

> ⚠️ **Wichtig:** `host` muss die lokale IP des Mac Mini sein (nicht 127.0.0.1), damit andere Geräte im Netzwerk die Bridge erreichen können!

**Python Path finden:**
```bash
which python3
# → /opt/homebrew/bin/python3 (macOS)
# → /usr/bin/python3 (Linux)
```

### 3. LaunchAgent einrichten (macOS)

Die LaunchAgent plist startet die Bridge automatisch beim Boot:

```bash
# plist anpassen (Pfade!)
nano com.openclaw.openai-bridge.plist

# LaunchAgent installieren
cp com.openclaw.openai-bridge.plist ~/Library/LaunchAgents/

# LaunchAgent laden und starten
launchctl load ~/Library/LaunchAgents/com.openclaw.openai-bridge.plist
launchctl start com.openclaw.openai-bridge
```

### 4. Linux systemd (alternative)

```bash
# Service file erstellen
sudo nano /etc/systemd/system/openclaw-openai-bridge.service

# Inhalt:
# [Unit]
# Description=OpenClaw OpenAI Bridge
# After=network.target

# [Service]
# ExecStart=/usr/bin/python3 /path/to/openai-openclaw-bridge-streaming.py
# WorkingDirectory=/path/to/openclaw-openai-bridge
# Restart=always

# [Install]
# WantedBy=multi-user.target

# Starten
sudo systemctl enable openclaw-openai-bridge
sudo systemctl start openclaw-openai-bridge
```

### 5. Status prüfen

```bash
# macOS
ps aux | grep "openai-openclaw-bridge"
launchctl list | grep openclaw

# Linux
sudo systemctl status openclaw-openai-bridge

# Logs
tail -f /path/to/openclaw-openai-bridge-streaming.log
```

## 🔧 Integration

### Open WebUI

In Open WebUI Settings → LLM:

```
[ ] Open AI API
✅ Custom API

API Provider: OpenAI
Base URL: http://192.168.1.XXX:9000/v1
API Key: (leer oder CONFIG["api_key"])
Model: openclaw
```

**Modell einrichten:**
```
Model Name: OpenClaw
Model ID: openclaw
```

### Home Assistant

1. **Custom Integration installieren:**
   ```bash
   # Via HACS oder manuell in config/www/
   # https://github.com/skye-harris/hass_local_openai_llm
   ```

2. **In HA Settings → LLM:**
   ```
   API Base URL: http://192.168.1.XXX:9000/v1
   API Key: (leer oder CONFIG["api_key"])
   Model: openclaw
   ```

## 📡 API Endpoints

### POST `/v1/chat/completions`

Chat Completion mit Streaming Support.

**Request:**
```json
{
  "model": "openclaw",
  "messages": [
    {"role": "user", "content": "Hallo"}
  ],
  "stream": true
}
```

**Response (Streaming):**
```
data: {"id":"chatcmpl-xxx","object":"chat.completion.chunk","created":1234567890,"model":"openclaw","choices":[{"index":0,"delta":{"role":"assistant","content":"Hi"},"finish_reason":null}]}
data: [DONE]
```

### GET `/v1/models`

Listet verfügbare Modelle.

**Response:**
```json
{
  "data": [{
    "id": "openclaw",
    "object": "model",
    "owned_by": "openclaw"
  }]
}
```

### GET `/health`

Health Check Endpoint.

**Response:**
```json
{"status": "ok", "timestamp": 1234567890}
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
tail -f /path/to/openclaw-openai-bridge-streaming.log
```

### Bridge neu starten

**macOS:**
```bash
launchctl stop com.openclaw.openai-bridge
launchctl start com.openclaw.openai-bridge
```

**Linux:**
```bash
sudo systemctl restart openclaw-openai-bridge
```

### Sessions aufräumen
```bash
openclaw sessions cleanup
```

## 🐛 Troubleshooting

### Bridge startet nicht
```bash
# LaunchAgent Status prüfen (macOS)
launchctl list | grep openai-bridge

# Manuell testen
python3 openai-openclaw-bridge-streaming.py
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
tail -50 /path/to/openclaw-openai-bridge-streaming.log

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
├── com.openclaw.openai-bridge.plist     # macOS LaunchAgent
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
