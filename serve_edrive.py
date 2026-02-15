#!/usr/bin/env python3
"""E-Drive HTML server with Ollama + SD WebUI CORS proxy.

Serves static files on port 8666 AND proxies:
  /ollama/*  →  Ollama at 127.0.0.1:11434
  /sd/*      →  SD WebUI at 127.0.0.1:7860
This eliminates all CORS issues by keeping everything same-origin.
"""
import http.server
import urllib.request
import urllib.error
import json
import os
import sys
import tempfile
import subprocess
import asyncio
import shutil

PORT = 8666
OLLAMA_BACKEND = "http://127.0.0.1:11434"
SD_BACKEND = "http://127.0.0.1:7860"
SERVE_DIR = os.path.dirname(os.path.abspath(__file__))
TTS_VOICE = os.environ.get("EDRIVE_TTS_VOICE", "en-GB-SoniaNeural")

# Route prefixes → backend URLs
PROXY_ROUTES = {
    "/ollama/": OLLAMA_BACKEND,
    "/sd/": SD_BACKEND,
}


class ProxyHandler(http.server.SimpleHTTPRequestHandler):
    """Serves static files and proxies /ollama/ and /sd/ requests."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=SERVE_DIR, **kwargs)

    # ── Proxy logic ──────────────────────────────────────────
    def _match_route(self):
        """Return (prefix, backend) if path matches a proxy route."""
        for prefix, backend in PROXY_ROUTES.items():
            if self.path.startswith(prefix):
                return prefix, backend
        return None, None

    def _proxy(self, method):
        prefix, backend = self._match_route()
        if not prefix:
            return False
        # Strip prefix, keep the rest (e.g. /ollama/api/tags → /api/tags)
        target = backend + self.path[len(prefix) - 1:]
        headers = {}
        for key in ("content-type", "accept", "authorization"):
            val = self.headers.get(key)
            if val:
                headers[key] = val

        body = None
        clen = self.headers.get("Content-Length")
        if clen:
            body = self.rfile.read(int(clen))

        req = urllib.request.Request(target, data=body, headers=headers, method=method)

        # Check if client wants streaming (Ollama generate uses stream:true)
        is_stream = False
        if body and method == "POST":
            try:
                payload = json.loads(body)
                is_stream = payload.get("stream", False)
            except Exception:
                pass

        try:
            resp = urllib.request.urlopen(req, timeout=300)
            if is_stream:
                # Stream response back chunk by chunk
                self.send_response(resp.status)
                ct = resp.headers.get("Content-Type", "application/x-ndjson")
                self.send_header("Content-Type", ct)
                self.send_header("Transfer-Encoding", "chunked")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                while True:
                    chunk = resp.read(4096)
                    if not chunk:
                        break
                    self.wfile.write(b"%x\r\n%b\r\n" % (len(chunk), chunk))
                    self.wfile.flush()
                self.wfile.write(b"0\r\n\r\n")
                self.wfile.flush()
                resp.close()
            else:
                data = resp.read()
                resp.close()
                self.send_response(resp.status)
                self.send_header("Content-Type", resp.headers.get("Content-Type", "application/json"))
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(data)
        except urllib.error.HTTPError as e:
            body_err = e.read()
            self.send_response(e.code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body_err)
        except Exception as e:
            self.send_response(502)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())
        return True

    def do_GET(self):
        # ── Health check endpoint ──
        if self.path == "/health":
            return self._handle_health()
        if not self._proxy("GET"):
            super().do_GET()

    # ── Health check endpoint ────────────────────────────────
    def _handle_health(self):
        """Return JSON status of backend services."""
        status = {"server": True, "ollama": False, "sd": False, "tts": False, "stt": False}
        # Check Ollama
        try:
            r = urllib.request.urlopen(OLLAMA_BACKEND + "/api/tags", timeout=3)
            status["ollama"] = r.status == 200
            r.close()
        except Exception:
            pass
        # Check SD WebUI
        try:
            r = urllib.request.urlopen(SD_BACKEND + "/internal/ping", timeout=3)
            status["sd"] = r.status == 200
            r.close()
        except Exception:
            pass
        # Check edge-tts availability
        try:
            import edge_tts  # noqa: F401
            status["tts"] = True
        except ImportError:
            pass
        # Check SpeechRecognition + ffmpeg
        try:
            import speech_recognition  # noqa: F401
            status["stt"] = shutil.which("ffmpeg") is not None
        except ImportError:
            pass
        body = json.dumps(status).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    # ── TTS endpoint (Edge TTS) ────────────────────────────
    def _handle_tts(self):
        clen = self.headers.get("Content-Length")
        if not clen:
            self._json_error(400, "no body")
            return
        body = self.rfile.read(int(clen))
        try:
            data = json.loads(body)
        except Exception:
            self._json_error(400, "invalid json")
            return
        text = data.get("text", "").strip()
        voice = data.get("voice", TTS_VOICE)
        if not text:
            self._json_error(400, "no text")
            return
        try:
            import edge_tts
        except ImportError:
            self._json_error(500, "edge-tts not installed — pip install edge-tts")
            return
        try:
            async def _synth():
                comm = edge_tts.Communicate(text, voice)
                audio = b""
                async for chunk in comm.stream():
                    if chunk["type"] == "audio":
                        audio += chunk["data"]
                return audio
            audio_bytes = asyncio.run(_synth())
            self.send_response(200)
            self.send_header("Content-Type", "audio/mpeg")
            self.send_header("Content-Length", str(len(audio_bytes)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(audio_bytes)
        except Exception as e:
            self._json_error(500, f"TTS failed: {e}")

    # ── STT endpoint (SpeechRecognition + ffmpeg) ────────────
    def _handle_stt(self):
        clen = self.headers.get("Content-Length")
        if not clen or int(clen) == 0:
            self._json_error(400, "no audio data")
            return
        audio_data = self.rfile.read(int(clen))
        if len(audio_data) < 100:
            self._json_error(400, "audio too short")
            return
        # Check ffmpeg
        if not shutil.which("ffmpeg"):
            self._json_error(500, "ffmpeg not installed — sudo apt install ffmpeg")
            return
        try:
            import speech_recognition as sr
        except ImportError:
            self._json_error(500, "SpeechRecognition not installed — pip install SpeechRecognition")
            return
        webm_path = wav_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as f:
                f.write(audio_data)
                webm_path = f.name
            wav_path = webm_path.replace(".webm", ".wav")
            result = subprocess.run(
                ["ffmpeg", "-y", "-i", webm_path, "-ar", "16000", "-ac", "1",
                 "-f", "wav", wav_path],
                capture_output=True, timeout=15
            )
            if result.returncode != 0:
                self._json_error(500, f"ffmpeg error: {result.stderr.decode()[:200]}")
                return
            recognizer = sr.Recognizer()
            recognizer.energy_threshold = 300
            with sr.AudioFile(wav_path) as source:
                audio = recognizer.record(source)
            text = recognizer.recognize_google(audio)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"text": text}).encode())
        except sr.UnknownValueError:
            self._json_error(200, "")
        except sr.RequestError as e:
            self._json_error(500, f"Google STT unavailable: {e}")
        except Exception as e:
            self._json_error(500, f"STT failed: {e}")
        finally:
            for p in [webm_path, wav_path]:
                if p:
                    try:
                        os.unlink(p)
                    except OSError:
                        pass

    def _json_error(self, code, msg):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps({"error": msg}).encode())

    def do_POST(self):
        if self.path == "/tts":
            return self._handle_tts()
        if self.path == "/stt":
            return self._handle_stt()
        if not self._proxy("POST"):
            self.send_response(405)
            self.end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Max-Age", "86400")
        self.end_headers()

    def log_message(self, fmt, *args):
        path = str(args[0]) if args else ""
        if "/ollama/" in path or "/sd/" in path:
            tag = "[OLLAMA]" if "/ollama/" in path else "[SD]"
            sys.stderr.write(f"{tag} {fmt % args}\n")
        elif "/tts" in path or "/stt" in path:
            tag = "[TTS]" if "/tts" in path else "[STT]"
            sys.stderr.write(f"{tag} {fmt % args}\n")


if __name__ == "__main__":
    os.chdir(SERVE_DIR)
    with http.server.ThreadingHTTPServer(("0.0.0.0", PORT), ProxyHandler) as httpd:
        print(f"[E-Drive Server] http://127.0.0.1:{PORT}/EDrive.html")
        print(f"[E-Drive Server] http://localhost:{PORT}/EDrive.html")
        print(f"[E-Drive Server] Ollama proxy: /ollama/* → {OLLAMA_BACKEND}/*")
        print(f"[E-Drive Server] SD proxy:     /sd/*     → {SD_BACKEND}/*")
        print(f"[E-Drive Server] TTS endpoint: /tts      (Edge TTS — {TTS_VOICE})")
        print(f"[E-Drive Server] STT endpoint: /stt      (SpeechRecognition + ffmpeg)")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n[E-Drive Server] Shutdown.")
