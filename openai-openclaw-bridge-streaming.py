#!/usr/bin/env python3
"""
OpenClaw OpenAI Bridge mit Streaming Support (Für hass_local_openai_llm)
=========================================================================
Bridge mit SSE (Server-Sent Events) Streaming - benötigt von HA Integration!

Funktionalität:
- Empfängt OpenAI Requests mit stream=true
- Ruft openclaw agent auf
- Sendet Antwort im Streaming Format (SSE)

Verwendung:
- hass_local_openai_llm erwartet Streaming!
- Base URL: http://192.168.178.5:9000/v1
"""

import http.server
import json
import subprocess
import sys
import os
import time
import uuid
import threading
from datetime import datetime
from io import StringIO

# Configuration
CONFIG = {
    "port": 9000,
    "host": "192.168.178.5",  # Mac Mini M4 IP
    "log_file": "/Users/elonseibot/.openclaw/workspace/logs/openclaw-openai-bridge-streaming.log",
    "api_key": None,
    "session_prefix": "ha-bridge",
    "timeout": 120,
}

def log(message):
    """Log messages to file and console"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] {message}"
    print(log_entry)
    sys.stdout.flush()
    
    os.makedirs(os.path.dirname(CONFIG["log_file"]), exist_ok=True)
    with open(CONFIG["log_file"], "a") as f:
        f.write(log_entry + "\n")

def call_openclaw_agent(messages):
    """
    Call OpenClaw via openclaw agent command.
    Returns list of text chunks for streaming.
    """
    try:
        user_message = messages[-1]["content"] if messages else "Hallo"
        
        # FIXE Session für HA → OpenClaw behält Context/Memory!
        session_id = "ha-bridge"
        
        log(f"OpenClaw agent call: session={session_id} (fixed), prompt={user_message[:100]}...")
        
        cmd = [
            "openclaw",
            "agent",
            "--session-id", session_id,
            "--message", user_message,
            "--json"
        ]
        
        log(f"Executing: {' '.join(cmd)}")
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=CONFIG["timeout"]
        )
        
        if result.returncode == 0:
            try:
                response_data = json.loads(result.stdout)
                
                if "result" in response_data and "payloads" in response_data["result"]:
                    payloads = response_data["result"]["payloads"]
                    if payloads and len(payloads) > 0:
                        response_text = payloads[0].get("text", "")
                        log(f"OpenClaw response received ({len(response_text)} chars)")
                        # SMART CHUNKING: Nur an WORD-GRENZEN splittern!
                        # Vermeidet: "Insta nz", "C ompanion", "Seibet Se ibets"
                        chunks = smart_chunk(response_text, chunk_size=40)
                        return chunks if chunks else [response_text]
                else:
                    log(f"Unexpected response format: {result.stdout[:200]}")
                    return ["OpenClaw error: Unexpected response format"]
                    
            except json.JSONDecodeError as e:
                log(f"OpenClaw JSON parse error: {str(e)}")
                return ["OpenClaw JSON parse error"]
        else:
            error_msg = f"OpenClaw error (code {result.returncode}): {result.stderr}"
            log(error_msg)
            return [error_msg]
            
    except subprocess.TimeoutExpired:
        log("OpenClaw call timed out")
        return ["OpenClaw call timed out"]
    except Exception as e:
        error_msg = f"OpenClaw call failed: {str(e)}"
        log(error_msg)
        return [error_msg]

def smart_chunk(text, chunk_size=40):
    """
    Split text into chunks at WORD BOUNDARIES.
    BEHALTE Leerzeichen zwischen Chunks! Wichtig für Streaming!
    
    Beispiel:
    "Hallo Welt wie gehts" → ["Hallo Welt", " wie gehts"]  ← Space am Anfang!
    NICHT: ["Hallo Welt", "wie gehts"]  ← Lückt!
    """
    if not text:
        return []
    
    chunks = []
    remaining = text
    
    while remaining:
        if len(remaining) <= chunk_size:
            # Letzter Chunk - kompletten Rest nehmen
            chunk = remaining
            if chunk:
                chunks.append(chunk)
            break
        
        # Versuche an Wortgrenze zu splittern
        # Suche letztes Leerzeichen innerhalb von chunk_size
        split_pos = remaining.rfind(' ', 0, chunk_size)
        
        if split_pos > 0:  # Gefunden und nicht am Anfang
            # Leerzeichen BEHALTEN - es geht zum NÄCHSTEN Chunk
            chunk = remaining[:split_pos]  # Kein rstrip!
            remaining = remaining[split_pos:]  # BEHALT Space am Anfang!
        else:
            # Keine Wortgrenze gefunden - forced split (z.B. bei sehr langen Wörtern)
            chunk = remaining[:chunk_size]
            remaining = remaining[chunk_size:]
        
        if chunk:
            chunks.append(chunk)
    
    return chunks

class StreamingBridgeHandler(http.server.BaseHTTPRequestHandler):
    """HTTP Request Handler mit Streaming Support"""
    
    def do_GET(self):
        """Handle GET requests"""
        if self.path == "/health" or self.path == "/":
            response = {
                "status": "ok",
                "service": "openclaw-openai-bridge-streaming",
                "version": "2.0.0"
            }
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())
            
        elif self.path == "/v1/models":
            response = {
                "object": "list",
                "data": [
                    {
                        "id": "seibot",
                        "object": "model",
                        "created": int(datetime.now().timestamp()),
                        "owned_by": "openclaw"
                    }
                ]
            }
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())
            
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_POST(self):
        """Handle POST requests"""
        if CONFIG["api_key"]:
            auth_header = self.headers.get("Authorization", "")
            if not auth_header.startswith("Bearer ") or auth_header[7:] != CONFIG["api_key"]:
                response = {"error": "Unauthorized"}
                self.send_response(401)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(response).encode())
                return
        
        if self.path == "/v1/chat/completions":
            try:
                content_length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(content_length)
                data = json.loads(body.decode())
                
                model = data.get("model", "seibot")
                messages = data.get("messages", [])
                max_tokens = data.get("max_tokens", 1000)
                stream = data.get("stream", False)  # ← Streaming Flag!
                
                # Handle multimodal messages (Text + Images!)
                timestamp = int(time.time())
                
                # CLEAN SESSION MANAGEMENT:
                # Client schickt GESAMTEN Chat-Verlauf → OpenClaw braucht KEIN Memory!
                # Jede Request = EIGENE Session → Context-Explosion vermieden!
                session_id = f"{CONFIG['session_prefix']}-{timestamp}"  # EINMALIG pro Request
                
                if isinstance(messages, list):
                    for msg in messages:
                        if isinstance(msg, dict) and isinstance(msg.get("content"), list):
                            text_parts = []
                            images = []  # Bilder sammeln!
                            
                            for item in msg["content"]:
                                if isinstance(item, dict):
                                    if item.get("type") == "text":
                                        text_parts.append(item.get("text", ""))
                                    elif item.get("type") == "image_url":
                                        # Open WebUI Format: {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,..."}}
                                        image_url = item.get("image_url", {}).get("url", "")
                                        if image_url:
                                            images.append(image_url)
                            
                            # Text zusammenfügen
                            msg["content"] = " ".join(text_parts)
                            
                            # Bilder als Base64 Data URLs - in Dateien speichern!
                            if images:
                                import base64
                                log(f"Image detected in message: {len(images)} image(s)")
                                
                                for i, img_url in enumerate(images):
                                    # Data URL entfernen (data:image/jpeg;base64,) → nur Base64
                                    if "," in img_url:
                                        base64_data = img_url.split(",", 1)[1]
                                    else:
                                        base64_data = img_url
                                    
                                    # Base64 in Datei speichern
                                    img_file = f"/tmp/openclaw-image-{timestamp}-{i}.jpg"
                                    try:
                                        with open(img_file, 'wb') as f:
                                            f.write(base64.b64decode(base64_data))
                                        
                                        # Pfad zum Prompt hinzufügen
                                        msg["content"] += f"\n\n[BILD {i+1}: {img_file}]"
                                        log(f"✅ Image saved: {img_file} ({len(base64_data)} bytes)")
                                    except Exception as e:
                                        log(f"❌ Image save error: {e}")
                                        msg["content"] += f"\n\n[BILD {i+1}: Base64 Fehler]"
                
                user_message = messages[-1]["content"] if messages else "Hallo"
                
                log(f"OpenAI request: model={model}, stream={stream}, messages={len(messages)}")
                
                if stream:
                    # Streaming response (SSE)
                    # ZUERST openclaw aufrufen WARTEN bis fertig!
                    response_text = " ".join(call_openclaw_agent(messages))
                    
                    # DANN streaming senden
                    self.send_response(200)
                    self.send_header("Content-Type", "text/event-stream")
                    self.send_header("Cache-Control", "no-cache")
                    self.send_header("Connection", "keep-alive")
                    self.end_headers()
                    
                    # SMART CHUNKING: Chunks aus response_text (an Wortgrenzen!)
                    response_chunks = smart_chunk(response_text, chunk_size=50)
                    
                    # Send initial delta
                    chunk_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
                    timestamp = int(datetime.now().timestamp())
                    
                    # First chunk with role
                    first_chunk = {
                        "id": chunk_id,
                        "object": "chat.completion.chunk",
                        "created": timestamp,
                        "model": model,
                        "choices": [{
                            "index": 0,
                            "delta": {"role": "assistant", "content": ""},
                            "finish_reason": None
                        }]
                    }
                    self.wfile.write(f"data: {json.dumps(first_chunk)}\n\n".encode())
                    
                    # Content chunks
                    for i, chunk_text in enumerate(response_chunks):
                        chunk = {
                            "id": chunk_id,
                            "object": "chat.completion.chunk",
                            "created": timestamp,
                            "model": model,
                            "choices": [{
                                "index": 0,
                                "delta": {"content": chunk_text},
                                "finish_reason": None
                            }]
                        }
                        self.wfile.write(f"data: {json.dumps(chunk)}\n\n".encode())
                        sys.stdout.flush()
                        time.sleep(0.05)  # Small delay for realistic streaming
                    
                    # Final chunk with finish_reason
                    final_chunk = {
                        "id": chunk_id,
                        "object": "chat.completion.chunk",
                        "created": timestamp,
                        "model": model,
                        "choices": [{
                            "index": 0,
                            "delta": {},
                            "finish_reason": "stop"
                        }]
                    }
                    self.wfile.write(f"data: {json.dumps(final_chunk)}\n\n".encode())
                    self.wfile.flush()
                    
                    # Done signal (EXAKT OpenAI Format!)
                    self.wfile.write(b"data: [DONE]\n\n")
                    self.wfile.flush()
                    
                    # Connection schließen
                    self.close_connection = True
                    
                    log("Streaming response sent + [DONE] + closed")
                    
                else:
                    # Non-streaming response
                    response_text = " ".join(call_openclaw_agent(messages))
                    
                    response = {
                        "id": f"chatcmpl-{uuid.uuid4().hex[:12]}",
                        "object": "chat.completion",
                        "created": int(datetime.now().timestamp()),
                        "model": model,
                        "choices": [{
                            "index": 0,
                            "message": {
                                "role": "assistant",
                                "content": response_text
                            },
                            "finish_reason": "stop"
                        }],
                        "usage": {
                            "prompt_tokens": sum(len(m.get("content", "")) for m in messages),
                            "completion_tokens": len(response_text),
                            "total_tokens": sum(len(m.get("content", "")) for m in messages) + len(response_text)
                        }
                    }
                    
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps(response).encode())
                
            except json.JSONDecodeError:
                response = {"error": "Invalid JSON"}
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(response).encode())
            except Exception as e:
                log(f"Error: {str(e)}")
                response = {"error": str(e)}
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(response).encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        """Override logging"""
        log(f"HTTP: {format % args}")

def run_bridge():
    """Start the Streaming Bridge server"""
    address = (CONFIG["host"], CONFIG["port"])
    server = http.server.HTTPServer(address, StreamingBridgeHandler)
    
    log(f"🚀 OpenClaw OpenAI Bridge (mit Streaming) gestartet")
    log(f"📡 URL: http://{CONFIG['host']}:{CONFIG['port']}")
    log(f"🔗 Endpoints:")
    log(f"   - POST /v1/chat/completions (streaming + non-streaming)")
    log(f"   - GET /v1/models")
    log(f"📝 Log: {CONFIG['log_file']}")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log("🛑 Bridge gestoppt")
        server.shutdown()

if __name__ == "__main__":
    run_bridge()
