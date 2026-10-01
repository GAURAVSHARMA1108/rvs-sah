"""
Main Application Launcher for RajPSP Student Profile Scraper
Desktop GUI built with PyWebView and Playwright Chromium automation.
Primary Colors: Signal Blue (#0057FF) and Porcelain (#F8F7F4).
"""

import os
import sys
import threading
import time
from pathlib import Path
from typing import Dict, List, Any, Optional

import webview

from browser_manager import BrowserManager, LOGIN_URL, PROFILE_URL
from exporter import export_to_excel, export_to_tsv


APP_DIR = Path(__file__).resolve().parent
WEB_DIR = APP_DIR / "web"
INDEX_HTML = WEB_DIR / "index.html"


class ScraperAppApi:
    """JavaScript API bridge exposed to the PyWebView frontend."""

    def __init__(self):
        self._lock = threading.Lock()
        self.logs: List[Dict[str, str]] = []
        self.browser_manager = BrowserManager(log_callback=self._log_callback)
        self.last_detected_table: Optional[Dict[str, Any]] = None
        self._auto_detect_flag = False

    def _log_callback(self, level: str, message: str, reason: str):
        with self._lock:
            self.logs.append({
                "level": level,
                "message": message,
                "reason": reason,
                "timestamp": time.strftime("%H:%M:%S")
            })

    def launch_browser(self) -> Dict[str, Any]:
        """Launches headed Chromium in a separate thread so GUI remains fluid."""
        result_holder = {}

        def _run():
            res = self.browser_manager.launch()
            result_holder["res"] = res

        t = threading.Thread(target=_run, daemon=True)
        t.start()
        t.join(timeout=30)
        return result_holder.get("res", {"success": False, "message": "Launch timeout or in progress."})

    def close_browser(self) -> Dict[str, Any]:
        """Closes browser session."""
        self.browser_manager.close()
        return {"success": True, "message": "Browser closed."}

    def navigate_to_profile_page(self) -> Dict[str, Any]:
        """Navigates to PSP_UpdateStudentProfileDataEntry.aspx."""
        return self.browser_manager.navigate_to_profile_page()

    def get_session_and_class_options(self) -> Dict[str, Any]:
        """Scans portal page for Session and Class dropdowns."""
        return self.browser_manager.get_session_and_class_options()

    def submit_session_and_class(self, session_val: str, class_val: str) -> Dict[str, Any]:
        """Submits session and class selection on portal and returns detected table."""
        res = self.browser_manager.submit_session_and_class(session_val, class_val)
        if res.get("found"):
            self.last_detected_table = res
        return res

    def detect_student_table(self) -> Dict[str, Any]:
        """Scans page DOM for student table."""
        res = self.browser_manager.detect_student_table()
        if res.get("found"):
            self.last_detected_table = res
        return res

    def deep_scrape_profiles(self, selected_indices: List[int]) -> Dict[str, Any]:
        """Deep scrapes full student profile forms for selected rows."""
        return self.browser_manager.deep_scrape_profiles(selected_indices)

    def export_to_excel(
        self,
        headers: List[str],
        rows: List[List[Any]],
        session_name: str = "",
        class_name: str = ""
    ) -> Dict[str, Any]:
        """Generates professionally styled Excel (.xlsx) file in Signal Blue #0057FF."""
        return export_to_excel(
            headers=headers,
            rows=rows,
            session_name=session_name,
            class_name=class_name
        )

    def copy_to_clipboard(self, headers: List[str], rows: List[List[Any]]) -> Dict[str, Any]:
        """Generates Tab-Separated Values (TSV) for clipboard copying."""
        tsv_str = export_to_tsv(headers, rows)
        return {
            "success": True,
            "tsv_data": tsv_str,
            "row_count": len(rows),
            "col_count": len(headers),
            "message": f"Formatted {len(rows)} records for clipboard.",
            "reason": "TSV string generated ready for Excel paste."
        }

    def poll_status(self, last_log_index: int = 0) -> Dict[str, Any]:
        """Polls backend status and retrieves new log messages."""
        with self._lock:
            total_logs = len(self.logs)
            new_logs = self.logs[last_log_index:] if last_log_index < total_logs else []
            next_index = total_logs

        return {
            "browser_running": self.browser_manager.is_running,
            "current_url": self.browser_manager.current_url,
            "login_detected": self.browser_manager.login_detected,
            "new_logs": new_logs,
            "next_log_index": next_index,
            "auto_table_detected": self._auto_detect_flag,
            "table_data": self.last_detected_table
        }

    def on_closing(self):
        """Cleanup handler when the desktop window is closed."""
        try:
            self.browser_manager.close()
        except Exception:
            pass


def main():
    if not INDEX_HTML.exists():
        print(f"Error: UI file not found at {INDEX_HTML}")
        sys.exit(1)

    api = ScraperAppApi()

    window = webview.create_window(
        title="RVS SAH | Rajasthan Portal Automation",
        url=str(INDEX_HTML),
        js_api=api,
        width=1240,
        height=820,
        min_size=(960, 620),
        background_color="#F8F7F4"  # Porcelain!
    )

    window.events.closing += api.on_closing

    print("=" * 70)
    print("RVS SAH is starting...")
    print("Primary Colors: Signal Blue (#0057FF) | Porcelain (#F8F7F4)")
    print("Login URL:  https://rajpsp.rajasthan.gov.in/home/schoollogin.aspx")
    print("Target URL: https://rajpsp.rajasthan.gov.in/School/PSP_UpdateStudentProfileDataEntry.aspx")
    print("=" * 70)

    webview.start(debug=False)


if __name__ == "__main__":
    main()
