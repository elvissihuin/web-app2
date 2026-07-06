# -*- coding: utf-8 -*-
"""
Social Media Video Downloader - Web Application
Flask backend with yt-dlp for downloading videos from
YouTube, TikTok, Facebook, and Pinterest.
"""

import os
import sys
import uuid
import json
import time
import threading
import tempfile
import shutil
from datetime import datetime

from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    send_file,
    Response,
    stream_with_context,
)

try:
    import yt_dlp
except ImportError:
    print("ERROR: yt-dlp no está instalado. Ejecuta: pip install yt-dlp")
    sys.exit(1)

# ──────────────────────────────────────────────
# App Configuration
# ──────────────────────────────────────────────

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024  # 16KB max request

# Store for download tasks (in-memory, keyed by task_id)
download_tasks = {}

# Temporary download directory
DOWNLOAD_DIR = os.path.join(tempfile.gettempdir(), "social_downloader")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# Resolution format mapping
RESOLUTION_MAP = {
    "best": "bestvideo+bestaudio/best",
    "2160": "bestvideo[height<=2160]+bestaudio/best[height<=2160]",
    "1440": "bestvideo[height<=1440]+bestaudio/best[height<=1440]",
    "1080": "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
    "720": "bestvideo[height<=720]+bestaudio/best[height<=720]",
    "480": "bestvideo[height<=480]+bestaudio/best[height<=480]",
    "360": "bestvideo[height<=360]+bestaudio/best[height<=360]",
}

# Platform detection patterns
PLATFORM_PATTERNS = {
    "youtube": ["youtube.com", "youtu.be", "youtube.com/shorts"],
    "tiktok": ["tiktok.com", "vm.tiktok.com"],
    "facebook": ["facebook.com", "fb.watch", "fb.com", "www.facebook.com"],
    "pinterest": ["pinterest.com", "pin.it", "pinterest.es", "pinterest.com.mx"],
}


def detect_platform(url):
    """Detect platform from URL."""
    url_lower = url.lower()
    for platform, patterns in PLATFORM_PATTERNS.items():
        for pattern in patterns:
            if pattern in url_lower:
                return platform
    return "unknown"


def clean_old_files():
    """Remove download files older than 30 minutes."""
    now = time.time()
    try:
        for fname in os.listdir(DOWNLOAD_DIR):
            fpath = os.path.join(DOWNLOAD_DIR, fname)
            if os.path.isfile(fpath):
                age = now - os.path.getmtime(fpath)
                if age > 1800:  # 30 minutes
                    os.remove(fpath)
    except Exception:
        pass


# ──────────────────────────────────────────────
# Routes
# ──────────────────────────────────────────────

@app.route("/")
def index():
    """Serve the main page."""
    return render_template("index.html")


@app.route("/api/info", methods=["POST"])
def get_video_info():
    """Get video information (title, thumbnail, available formats)."""
    data = request.get_json()
    url = data.get("url", "").strip()

    if not url:
        return jsonify({"error": "URL vacía"}), 400

    platform = detect_platform(url)
    if platform == "unknown":
        return jsonify({"error": "URL no soportada. Usa URLs de YouTube, TikTok, Facebook o Pinterest."}), 400

    try:
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "nocheckcertificate": True,
            "skip_download": True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        # Collect available resolutions
        formats = info.get("formats", [])
        available_heights = set()
        for f in formats:
            h = f.get("height")
            if h and h > 0:
                available_heights.add(h)

        # Standard resolutions that are available
        standard_res = [2160, 1440, 1080, 720, 480, 360]
        available_res = [r for r in standard_res if r in available_heights]

        result = {
            "title": info.get("title", "Sin título"),
            "thumbnail": info.get("thumbnail", ""),
            "duration": info.get("duration", 0),
            "uploader": info.get("uploader", "Desconocido"),
            "platform": platform,
            "available_resolutions": available_res,
            "description": (info.get("description", "") or "")[:200],
        }

        return jsonify(result)

    except Exception as e:
        return jsonify({"error": f"No se pudo obtener la información: {str(e)[:150]}"}), 500


@app.route("/api/download", methods=["POST"])
def start_download():
    """Start a download and return a task ID for tracking progress."""
    data = request.get_json()
    url = data.get("url", "").strip()
    resolution = data.get("resolution", "best")
    audio_mode = data.get("audio_mode", "best")  # best, mp3, m4a
    platform = data.get("platform", detect_platform(url))

    if not url:
        return jsonify({"error": "URL vacía"}), 400

    task_id = str(uuid.uuid4())[:8]

    # Initialize task state
    download_tasks[task_id] = {
        "status": "starting",
        "progress": 0,
        "speed": "",
        "eta": "",
        "filename": "",
        "title": "",
        "error": "",
        "filepath": "",
        "completed": False,
    }

    # Start download in background thread
    thread = threading.Thread(
        target=_download_worker,
        args=(task_id, url, resolution, audio_mode, platform),
        daemon=True,
    )
    thread.start()

    return jsonify({"task_id": task_id})


@app.route("/api/progress/<task_id>")
def progress_stream(task_id):
    """SSE stream for download progress."""
    def generate():
        if task_id not in download_tasks:
            yield f"data: {json.dumps({'error': 'Task not found'})}\n\n"
            return

        last_progress = -1
        while True:
            task = download_tasks.get(task_id)
            if not task:
                break

            current_progress = task["progress"]

            # Send update if progress changed or status changed
            if current_progress != last_progress or task["status"] in ("completed", "error"):
                event_data = {
                    "status": task["status"],
                    "progress": task["progress"],
                    "speed": task["speed"],
                    "eta": task["eta"],
                    "title": task["title"],
                    "filename": task["filename"],
                }

                if task["status"] == "error":
                    event_data["error"] = task["error"]

                yield f"data: {json.dumps(event_data)}\n\n"
                last_progress = current_progress

            if task["status"] in ("completed", "error"):
                break

            time.sleep(0.5)

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@app.route("/api/file/<task_id>")
def serve_file(task_id):
    """Serve the downloaded file."""
    task = download_tasks.get(task_id)
    if not task:
        return jsonify({"error": "Task not found"}), 404

    if not task["completed"]:
        return jsonify({"error": "Download not completed yet"}), 400

    filepath = task["filepath"]
    if not filepath or not os.path.exists(filepath):
        return jsonify({"error": "File not found"}), 404

    filename = task["filename"] or os.path.basename(filepath)

    # Clean old files in background
    threading.Thread(target=clean_old_files, daemon=True).start()

    return send_file(
        filepath,
        as_attachment=True,
        download_name=filename,
    )


# ──────────────────────────────────────────────
# Download Worker
# ──────────────────────────────────────────────

def _download_worker(task_id, url, resolution, audio_mode, platform):
    """Background worker that performs the actual download."""
    task = download_tasks[task_id]
    task["status"] = "downloading"

    # Create a unique subdirectory for this download
    task_dir = os.path.join(DOWNLOAD_DIR, task_id)
    os.makedirs(task_dir, exist_ok=True)

    outtmpl = os.path.join(task_dir, "%(title)s.%(ext)s")

    def progress_hook(d):
        if d["status"] == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            downloaded = d.get("downloaded_bytes", 0)

            if total > 0:
                pct = int((downloaded / total) * 100)
            else:
                pct_str = d.get("_percent_str", "0%").strip()
                try:
                    pct = int(float(pct_str.replace("%", "")))
                except ValueError:
                    pct = 0

            task["progress"] = min(pct, 99)
            task["speed"] = d.get("_speed_str", "").strip()
            task["eta"] = d.get("_eta_str", "").strip()
            task["status"] = "downloading"

        elif d["status"] == "finished":
            task["progress"] = 95
            task["status"] = "processing"

    try:
        # Build yt-dlp options
        ydl_opts = {
            "outtmpl": outtmpl,
            "merge_output_format": "mp4",
            "progress_hooks": [progress_hook],
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "nocheckcertificate": True,
        }

        # Platform-specific options
        if platform == "tiktok":
            ydl_opts["format"] = "best"
        elif audio_mode == "mp3":
            ydl_opts["format"] = "bestaudio/best"
            ydl_opts["postprocessors"] = [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "320",
            }]
        elif audio_mode == "m4a":
            ydl_opts["format"] = "bestaudio/best"
            ydl_opts["postprocessors"] = [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "m4a",
                "preferredquality": "0",
            }]
        else:
            fmt = RESOLUTION_MAP.get(resolution, RESOLUTION_MAP["best"])
            ydl_opts["format"] = fmt

        # Add metadata postprocessor
        if "postprocessors" not in ydl_opts:
            ydl_opts["postprocessors"] = []
        ydl_opts["postprocessors"].append({"key": "FFmpegMetadata"})

        # Extract info first to get title
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            task["title"] = info.get("title", "Video")

            # Now download
            ydl.download([url])

        # Find the downloaded file
        downloaded_file = None
        for fname in os.listdir(task_dir):
            fpath = os.path.join(task_dir, fname)
            if os.path.isfile(fpath):
                downloaded_file = fpath
                break

        if downloaded_file:
            task["filepath"] = downloaded_file
            task["filename"] = os.path.basename(downloaded_file)
            task["progress"] = 100
            task["status"] = "completed"
            task["completed"] = True
        else:
            task["status"] = "error"
            task["error"] = "No se encontró el archivo descargado"

    except Exception as e:
        task["status"] = "error"
        task["error"] = str(e)[:200]


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print("\n" + "=" * 55)
    print("   Social Media Video Downloader - Web")
    print(f"   Abre en tu navegador: http://localhost:{port}")
    print("=" * 55 + "\n")
    app.run(host="0.0.0.0", port=port, debug=False)
