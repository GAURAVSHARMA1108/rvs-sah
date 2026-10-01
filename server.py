"""
Web Server for RajPSP Student Profile Scraper
Runs a real Bottle HTTP server connecting the in-dashboard login and scraper UI
directly to background Playwright Chromium automation and openpyxl Excel generation.
Strictly ZERO mock data.
"""

import os
import sys
import time
import threading
from pathlib import Path
from socketserver import ThreadingMixIn
from wsgiref.simple_server import make_server, WSGIServer, WSGIRequestHandler
from bottle import Bottle, static_file, request, response, run, ServerAdapter

class QuietHandler(WSGIRequestHandler):
    def log_message(self, format, *args):
        pass

class ThreadingWSGIServer(ThreadingMixIn, WSGIServer):
    daemon_threads = True

class ThreadedWSGIServerAdapter(ServerAdapter):
    def run(self, handler):
        server = make_server(self.host, self.port, handler, server_class=ThreadingWSGIServer, handler_class=QuietHandler)
        server.serve_forever()

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

from browser_manager import BrowserManager, LOGIN_URL, PROFILE_URL
from exporter import export_to_excel, export_to_tsv

APP_DIR = Path(__file__).resolve().parent
WEB_DIR = APP_DIR / "web"

app = Bottle()

log_lock = threading.Lock()
server_logs = []

def server_log_callback(level: str, message: str, reason: str):
    with log_lock:
        server_logs.append({
            "level": level,
            "message": message,
            "reason": reason,
            "timestamp": time.strftime("%H:%M:%S")
        })

browser_manager = BrowserManager(log_callback=server_log_callback)


@app.route("/")
def index():
    return static_file("index.html", root=str(WEB_DIR))


@app.route("/<filepath:path>")
def server_static(filepath):
    return static_file(filepath, root=str(WEB_DIR))


# In-Dashboard Login Endpoints
@app.route("/api/init-login", method="POST")
def handle_init_login():
    response.content_type = "application/json"
    res = browser_manager.init_login_session()
    return res


@app.route("/api/refresh-captcha", method="POST")
def handle_refresh_captcha():
    response.content_type = "application/json"
    res = browser_manager.refresh_captcha()
    return res


@app.route("/api/check-school-code", method="POST")
def handle_check_school():
    response.content_type = "application/json"
    data = request.json or {}
    username = data.get("username", "")
    res = browser_manager.check_school_code(username)
    return res


@app.route("/api/submit-login", method="POST")
def handle_submit_login():
    response.content_type = "application/json"
    data = request.json or {}
    username = data.get("username", "")
    password = data.get("password", "")
    captcha = data.get("captcha", "")
    res = browser_manager.submit_login(username, password, captcha)
    return res


@app.route("/api/close-browser", method="POST")
def handle_close():
    response.content_type = "application/json"
    res = browser_manager.close()
    return res


@app.route("/api/get-dropdowns", method="GET")
def handle_get_dropdowns():
    response.content_type = "application/json"
    res = browser_manager.get_session_and_class_options()
    return res


@app.route("/api/submit-view", method="POST")
def handle_submit_view():
    response.content_type = "application/json"
    data = request.json or {}
    session_val = data.get("sessionVal", "")
    class_val = data.get("classVal", "")
    res = browser_manager.submit_session_and_class(session_val, class_val)
    return res


@app.route("/api/detect-table", method="GET")
def handle_detect_table():
    response.content_type = "application/json"
    res = browser_manager.detect_student_table()
    return res


@app.route("/api/deep-scrape", method="POST")
def handle_deep_scrape():
    response.content_type = "application/json"
    data = request.json or {}
    indices = data.get("indices", [])
    res = browser_manager.deep_scrape_profiles(indices)
    return res


@app.route("/api/export-excel", method="POST")
def handle_export_excel():
    try:
        data = request.json or {}
        headers = data.get("headers", [])
        rows = data.get("rows", [])
        session_name = data.get("sessionName", "2024-25")
        class_name = data.get("className", "Class1")

        if not headers or not rows:
            response.status = 400
            return {"error": "Missing headers or rows to export."}

        temp_dir = APP_DIR / "temp_exports"
        temp_dir.mkdir(exist_ok=True)
        clean_sess = "".join(c for c in session_name if c.isalnum() or c in ("-", "_")).strip()
        clean_cls = "".join(c for c in class_name if c.isalnum() or c in ("-", "_")).strip()
        filename = f"PSP_Student_Profiles_{clean_sess}_{clean_cls}.xlsx"
        target_path = str(temp_dir / filename)

        res = export_to_excel(
            headers=headers,
            rows=rows,
            output_path=target_path,
            session_name=session_name,
            class_name=class_name
        )

        if not res.get("success"):
            response.status = 500
            return {"error": res.get("message")}

        return static_file(
            filename,
            root=str(temp_dir),
            download=filename,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    except Exception as e:
        response.status = 500
        return {"error": str(e)}


@app.route("/api/poll-status", method="GET")
def handle_poll():
    response.content_type = "application/json"
    last_idx = int(request.query.get("last_index", 0))

    with log_lock:
        total = len(server_logs)
        new_logs = server_logs[last_idx:] if last_idx < total else []
        next_idx = total

    status = browser_manager.get_status()
    return {
        "browser_running": status.get("browser_running", False),
        "current_url": status.get("current_url", ""),
        "login_detected": status.get("login_detected", False),
        "school_user": status.get("school_user", ""),
        "school_name": status.get("school_name", ""),
        "new_logs": new_logs,
        "next_log_index": next_idx
    }


if __name__ == "__main__":
    print("=" * 70)
    print("RajPSP Student Profile Scraper - In-Dashboard Authentication Server")
    print("Listening on: http://localhost:8085")
    print("Primary Colors: Signal Blue (#0057FF) / Porcelain (#F8F7F4)")
    print("Strictly ZERO MOCK DATA - Real Live Portal Captcha & Execution")
    print("=" * 70)
    run(app, host="0.0.0.0", port=8085, server=ThreadedWSGIServerAdapter, quiet=True)
