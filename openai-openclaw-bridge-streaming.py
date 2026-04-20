#!/usr/bin/env python3
"""
OpenClaw OpenAI Bridge mit Streaming Support
=============================================
Bridge mit SSE (Server-Sent Events) Streaming - benötigt von HA Integration!

Funktionalität:
- Empfängt OpenAI Requests mit stream=true
- Ruft openclaw agent auf
- Sendet Antwort im Streaming Format (SSE)
- Unterstützt multimodale Inputs (Bilder)

Verwendung:
- Open WebUI als Chat UI mit OpenClaw
- Home Assistant als LLM Provider
- Jeder OpenAI-kompatible Client
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

# Configuration - ANPASSEN!
CONFIG = {
    "port": 9000,                    # Port der Bridge
    "host": "192.168.1.XXX",         # IP des Mac Mini (lokal!)
    "log_file": "/path/to/openclaw-openai-bridge-streaming.log",  # Log Pfad
    "api_key": None,                 # Optional: API Key für Auth
    "session_prefix": "openclaw",     # Session Prefix
    "timeout": 120,                  # Timeout in Sekunden
}

def log(message):
    """Log messages to file and console"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] {message}"
    
    # Console
    print(log_entry, flush=True)
    
    # File
    try:
        with open(CONFIG["log_file"], "a") as f:
            f.write(log_entry + "\n")
    except Exception as e:
        print(f"Log error: {e}", flush=True)

class OpenAIBridgeHandler(http.server.BaseHTTPRequestHandler):
    """HTTP Handler für die OpenAI Bridge"""
    
    def log_message(self, format, *args):
        """Custom logging"""
        log(f"HTTP: {format % args}")
    
    def send_json(self, status_code, data):
        """Send JSON response"""
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    
    def send_sse(self, data):
        """Send SSE chunk"""
        if isinstance(data, dict):
            data = json.dumps(data)
        self.wfile.write(f"data: {data}\n\n".encode())
        self.wfile.flush()
    
    def do_GET(self):
        """Handle GET requests"""
        if self.path == "/v1/models":
            # Models endpoint
            response = {
                "data": [{
                    "id": "openclaw",
                    "object": "model",
                    "owned_by": "openclaw",
                    "created": int(time.time()),
                    "permissions": {}
                }]
            }
            self.send_json(200, response)
        
        elif self.path == "/health":
            # Health check
            self.send_json(200, {"status": "ok", "timestamp": time.time()})
        
        else:
            self.send_json(404, {"error": "Not found"})
    
    def do_POST(self):
        """Handle POST requests"""
        if CONFIG["api_key"]:
            auth_header = self.headers.get("Authorization", "")
            if not auth_header.startswith("Bearer ") or auth_header[7:] != CONFIG["api_key"]:
                self.send_json(401, {"error": "Unauthorized"})
                return
        
        if self.path == "/v1/chat/completions":
            try:
                content_length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(content_length)
                data = json.loads(body.decode())
                
                model = data.get("model", "openclaw")
                messages = data.get("messages", [])
                max_tokens = data.get("max_tokens", 1000)
                stream = data.get("stream", False)
                
                # Handle multimodal messages (Text + Images!)
                timestamp = int(time.time())
                if isinstance(messages, list):
                    for msg in messages:
                        if isinstance(msg, dict) and isinstance(msg.get("content"), list):
                            text_parts = []
                            images = []
                            
                            for item in msg["content"]:
                                if isinstance(item, dict):
                                    if item.get("type") == "text":
                                        text_parts.append(item.get("text", ""))
                                    elif item.get("type") == "image_url":
                                        image_url = item.get("image_url", {}).get("url", "")
                                        if image_url:
                                            images.append(image_url)
                            
                            msg["content"] = " ".join(text_parts)
                            
                            if images:
                                import base64
                                log(f"Image detected: {len(images)} image(s)")
                                
                                for i, img_url in enumerate(images):
                                    if "," in img_url:
                                        base64_data = img_url.split(",", 1)[1]
                                    else:
                                        base64_data = img_url
                                    
                                    img_file = f"/tmp/openclaw-image-{timestamp}-{i}.jpg"
                                    try:
                                        with open(img_file, 'wb') as f:
                                            f.write(base64.b64decode(base64_data))
                                        
                                        msg["content"] += f"\n\n[IMAGE {i+1}: {img_file}]"
                                        log(f"Image saved: {img_file}")
                                    except Exception as e:
                                        log(f"Image error: {e}")
                
                user_message = messages[-1]["content"] if messages else "Hallo"
                
                log(f"OpenAI request: model={model}, stream={stream}")
                
                if stream:
                    # Streaming response (SSE)
                    self.send_response(200)
                    self.send_header("Content-Type", "text/event-stream")
                    self.send_header("Cache-Control", "no-cache")
                    self.send_header("Connection", "keep-alive")
                    self.end_headers()
                    
                    chunk_id = f"chatcmpl-{uuid.uuid4().hex[:8]}"
                    
                    # Call OpenClaw
                    result = subprocess.run(
                        ["openclaw", "agent", "--session-id", f"{CONFIG['session_prefix']}-{timestamp}", "--message", user_message, "--json"],
                        capture_output=True, text=True, timeout=CONFIG["timeout"]
                    )
                    
                    if result.returncode != 0:
                        error_msg = f"OpenClaw error: {result.stderr}"
                        log(error_msg)
                        error_chunk = {
                            "id": chunk_id,
                            "object": "chat.completion.chunk",
                            "created": int(time.time()),
                            "model": model,
                            "choices": [{"index": 0, "delta": {"content": error_msg}, "finish_reason": None}]
                        }
                        self.send_sse(error_chunk)
                    
                    else:
                        response_text = result.stdout.strip()
                        
                        # Smart chunking
                        chunks = smart_chunk(response_text)
                        
                        for i, chunk_text in enumerate(chunks):
                            chunk = {
                                "id": chunk_id,
                                "object": "chat.completion.chunk",
                                "created": int(time.time()),
                                "model": model,
                                "choices": [{
                                    "index": 0,
                                    "delta": {"content": chunk_text},
                                    "finish_reason": None
                                }]
                            }
                            self.send_sse(chunk)
                            
                            if i < len(chunks) - 1:
                                time.sleep(0.05)
                        
                        # Final chunk
                        final_chunk = {
                            "id": chunk_id,
                            "object": "chat.completion.chunk",
                            "created": int(time.time()),
                            "model": model,
                            "choices": [{
                                "index": 0,
                                "delta": {},
                                "finish_reason": "stop"
                            }]
                        }
                        self.send_sse(final_chunk)
                        
                        # Done signal
                        self.send_sse("[DONE]")
                        self.close_connection = True
                        
                        log("Streaming response sent")
                
                else:
                    # Non-streaming response
                    result = subprocess.run(
                        ["openclaw", "agent", "--session-id", f"{CONFIG['session_prefix']}-{timestamp}", "--message", user_message, "--json"],
                        capture_output=True, text=True, timeout=CONFIG["timeout"]
                    )
                    
                    if result.returncode != 0:
                        response = {"error": result.stderr}
                        self.send_json(500, response)
                    else:
                        response_text = result.stdout.strip()
                        response = {
                            "id": f"chatcmpl-{uuid.uuid4().hex[:8]}",
                            "object": "chat.completion",
                            "created": int(time.time()),
                            "model": model,
                            "choices": [{
                                "index": 0,
                                "message": {"role": "assistant", "content": response_text},
                                "finish_reason": "stop"
                            }]
                        }
                        self.send_json(200, response)
            
            except subprocess.TimeoutExpired:
                log("OpenClaw call timed out")
                self.send_json(504, {"error": "Timeout"})
            
            except Exception as e:
                log(f"Error: {str(e)}")
                self.send_json(500, {"error": str(e)})
        
        else:
            self.send_json(404, {"error": "Not found"})

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
            chunk = remaining
            if chunk:
                chunks.append(chunk)
            break
        
        split_pos = remaining.rfind(' ', 0, chunk_size)
        
        if split_pos > 0:
            chunk = remaining[:split_pos]
            remaining = remaining[split_pos:]
        else:
            chunk = remaining[:chunk_size]
            remaining = remaining[chunk_size:]
        
        if chunk:
            chunks.append(chunk)
    
    return chunks

def run_server():
    """Start HTTP Server"""
    server = http.server.HTTPServer((CONFIG["host"], CONFIG["port"]), OpenAIBridgeHandler)
    
    log(f"🚀 OpenClaw OpenAI Bridge gestartet")
    log(f"📡 URL: http://{CONFIG['host']}:{CONFIG['port']}")
    log(f"📝 Log: {CONFIG['log_file']}")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log("Server stopped")
        server.server_close()

if __name__ == "__main__":
    run_server()
