"""
Multi-Tenant Browser Context Pool for RVS SAH API.
Maintains a shared background Playwright Chromium process and provisions
lightweight, isolated BrowserContexts per client session token.
Includes automatic idle-session cleanup and concurrency management.
"""

import time
import base64
import queue
import secrets
import threading
import concurrent.futures
from typing import Dict, List, Any, Optional, Tuple
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page
from .ocr_solver import solve_captcha_from_base64

LOGIN_URL = "https://rajpsp.rajasthan.gov.in/home/schoollogin.aspx"
PROFILE_URL = "https://rajpsp.rajasthan.gov.in/School/PSP_UpdateStudentProfileDataEntry.aspx"

SESSION_TIMEOUT_SECONDS = 300  # 5 minutes idle timeout


class BrowserSession:
    def __init__(self, session_id: str, context: BrowserContext, page: Page):
        self.session_id = session_id
        self.context = context
        self.page = page
        self.created_at = time.time()
        self.last_active = time.time()
        self.is_logged_in = False
        self.school_code = ""
        self.school_name = ""
        self.lock = threading.Lock()

    def touch(self):
        self.last_active = time.time()

    def is_expired(self) -> bool:
        return (time.time() - self.last_active) > SESSION_TIMEOUT_SECONDS

    def close(self):
        try:
            self.page.close()
        except Exception:
            pass
        try:
            self.context.close()
        except Exception:
            pass


class BrowserContextPool:
    """Thread-safe pool managing Playwright browser worker and user contexts."""

    _instance = None
    _init_lock = threading.Lock()

    def __new__(cls):
        with cls._init_lock:
            if cls._instance is None:
                cls._instance = super(BrowserContextPool, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if getattr(self, '_initialized', False):
            return
        self._initialized = True

        self.task_queue = queue.Queue()
        self.sessions: Dict[str, BrowserSession] = {}
        self.sessions_lock = threading.Lock()

        # Dedicated worker thread for Playwright event loop
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True, name="PlaywrightPoolWorker")
        self.worker_thread.start()

        # Cleaner thread to prune expired sessions
        self.cleaner_thread = threading.Thread(target=self._cleanup_loop, daemon=True, name="SessionReaper")
        self.cleaner_thread.start()

    def _worker_loop(self):
        with sync_playwright() as p:
            self.playwright = p
            self.browser = p.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox", "--disable-dev-shm-usage"]
            )
            print("[BrowserContextPool] Shared Chromium automation engine initialized.")

            while True:
                task = self.task_queue.get()
                if task is None:
                    break
                fn, future = task
                try:
                    res = fn()
                    future.set_result(res)
                except Exception as e:
                    future.set_exception(e)
                finally:
                    self.task_queue.task_done()

            # Shutdown cleanup
            try:
                self.browser.close()
            except Exception:
                pass

    def _execute(self, fn, timeout: float = 60.0) -> Any:
        future = concurrent.futures.Future()
        self.task_queue.put((fn, future))
        try:
            return future.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            return {"success": False, "error": f"Operation timed out ({timeout}s)."}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _cleanup_loop(self):
        while True:
            time.sleep(30)
            expired = []
            with self.sessions_lock:
                for sid, s in list(self.sessions.items()):
                    if s.is_expired():
                        expired.append(sid)

            for sid in expired:
                self.close_session(sid)

    # =========================================================================
    # PUBLIC POOL API
    # =========================================================================

    def create_session(self) -> Dict[str, Any]:
        """Creates an isolated BrowserContext and navigates to the login page."""
        def _task():
            session_id = secrets.token_hex(16)
            context = self.browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 800}
            )
            page = context.new_page()
            page.goto(LOGIN_URL, timeout=45000, wait_until="domcontentloaded")
            time.sleep(1.0)

            # Capture initial captcha
            captcha_b64 = self._extract_captcha(page)

            bs = BrowserSession(session_id, context, page)
            with self.sessions_lock:
                self.sessions[session_id] = bs

            return {
                "success": True,
                "session_id": session_id,
                "captcha_b64": captcha_b64,
                "message": "Session initialized with live CAPTCHA."
            }

        return self._execute(_task, timeout=45.0)

    def refresh_captcha(self, session_id: str) -> Dict[str, Any]:
        """Refreshes the live CAPTCHA for an existing session."""
        def _task():
            session = self._get_session(session_id)
            if not session:
                return {"success": False, "error": "Invalid or expired session ID."}

            session.touch()
            page = session.page

            # Try clicking refresh button on portal or reload page
            refreshed = False
            for sel in ["#btnRefresh", "#imgbtnRefresh", "a[id*='refresh' i]", "input[id*='refresh' i]"]:
                if page.query_selector(sel):
                    try:
                        page.click(sel, timeout=3000)
                        refreshed = True
                        break
                    except Exception:
                        pass

            if not refreshed:
                page.reload(wait_until="domcontentloaded", timeout=30000)

            time.sleep(1.0)
            captcha_b64 = self._extract_captcha(page)
            return {
                "success": True,
                "session_id": session_id,
                "captcha_b64": captcha_b64
            }

        return self._execute(_task, timeout=30.0)

    def submit_login(self, session_id: str, username: str, password: str, captcha: str) -> Dict[str, Any]:
        """Submits credentials and authenticates against the live portal."""
        def _task():
            session = self._get_session(session_id)
            if not session:
                return {"success": False, "error": "Session expired or not found."}

            session.touch()
            page = session.page

            # Check if already at profile page
            if "PSP_UpdateStudentProfileDataEntry.aspx" in page.url:
                session.is_logged_in = True
                opts = self._scrape_dropdowns(page)
                return {
                    "success": True,
                    "already_logged_in": True,
                    "school_code": session.school_code or username,
                    "school_name": session.school_name or username,
                    "sessions": opts["sessions"],
                    "classes": opts["classes"]
                }

            current_url = (page.url or "").lower()
            if "schoollogin.aspx" not in current_url:
                page.goto(LOGIN_URL, timeout=35000, wait_until="domcontentloaded")
                time.sleep(1.0)

            clean_user = username.strip()
            clean_pwd = password.strip()
            clean_captcha = captcha.strip()

            # Capture alerts / dialogs from actual government portal
            dialog_messages = []
            def _handle_dialog(dialog):
                dialog_messages.append(dialog.message)
                try:
                    dialog.accept()
                except Exception:
                    pass

            page.on("dialog", _handle_dialog)

            try:
                # 1. Resolve School PSP Code to internal user ID & trigger ASP.NET salt fetch
                current_uname = page.evaluate("() => document.getElementById('txtUNameschool')?.value")
                current_uid = page.evaluate("() => document.getElementById('hdnUserIdschool')?.value")

                if current_uname != clean_user or not current_uid:
                    page.fill("#txtUNameschool", clean_user)
                    page.evaluate("() => document.getElementById('txtUNameschool').dispatchEvent(new Event('change', { bubbles: true }))")

                    # Wait for hdnUserIdschool to be populated or an alert dialog
                    start_res = time.time()
                    while time.time() - start_res < 6.0:
                        if dialog_messages:
                            break
                        uid = page.evaluate("() => document.getElementById('hdnUserIdschool')?.value")
                        if uid:
                            break
                        page.wait_for_timeout(250)

                    if dialog_messages:
                        err_msg = " | ".join(dialog_messages)
                        new_cap = self._extract_captcha(page)
                        return {
                            "success": False,
                            "error": err_msg,
                            "captcha_b64": new_cap
                        }

                resolved_uid = page.evaluate("() => document.getElementById('hdnUserIdschool')?.value") or clean_user

                # 2. Inject password, compute exact salted SHA-512 hash, and set captcha
                inject_res = page.evaluate("""(args) => {
                    const pwdEl = document.getElementById('txtUPswdschool');
                    if (pwdEl) {
                        pwdEl.onblur = null;
                        pwdEl.removeAttribute('onblur');
                    }

                    const capEl = document.getElementById('txtschool_Captcha');
                    if (capEl) capEl.value = args.captcha;

                    const u = document.getElementById('hdnUserIdschool')?.value || args.username.trim();
                    const rand = document.getElementById('hdnRandNu512')?.value || '';
                    const p = args.password;

                    if (typeof SHA512 === 'function') {
                        const pSha = SHA512(p);
                        const hdnDempps = document.getElementById('hdnDempps');
                        if (hdnDempps) hdnDempps.value = pSha;
                        const hdnDemppsSha512 = document.getElementById('hdnDemppsSha512');
                        if (hdnDemppsSha512) hdnDemppsSha512.value = pSha;

                        const sha = SHA512(u.toLowerCase() + p);
                        const hashs = SHA512(rand + sha);
                        if (pwdEl) pwdEl.value = hashs;
                    }

                    if (typeof Page_ClientValidate === 'function') Page_ClientValidate('val');
                    if (typeof Page_Validators !== 'undefined') {
                        Page_Validators.forEach(v => { v.isvalid = true; });
                    }

                    return {
                        uid: u,
                        pwdLen: document.getElementById('txtUPswdschool')?.value?.length,
                        c: document.getElementById('txtschool_Captcha')?.value
                    };
                }""", {"password": clean_pwd, "captcha": clean_captcha, "username": clean_user})

                dialog_messages.clear()

                # 3. Click login button (#btnloginschool)
                btn = page.query_selector("#btnloginschool, input[name*='btnloginschool']")
                if btn:
                    btn.click()
                else:
                    page.keyboard.press("Enter")

                # Settle response or dialog alert
                start_wait = time.time()
                while time.time() - start_wait < 10.0:
                    if dialog_messages:
                        break
                    url_now = (page.url or "").lower()
                    if "schoollogin.aspx" not in url_now:
                        break
                    page.wait_for_timeout(250)

                current_url = page.url
                url_lower = current_url.lower()

                # Success check: navigated past schoollogin.aspx without error
                if "schoollogin.aspx" not in url_lower and "error_page.aspx" not in url_lower:
                    session.is_logged_in = True
                    session.school_code = clean_user

                    school_name = self._extract_school_name(page)
                    session.school_name = school_name or clean_user

                    # Navigate to profile entry page
                    if "PSP_UpdateStudentProfileDataEntry.aspx" not in current_url:
                        page.goto(PROFILE_URL, timeout=45000, wait_until="domcontentloaded")
                        time.sleep(1.0)

                    opts = self._scrape_dropdowns(page)
                    return {
                        "success": True,
                        "school_code": session.school_code,
                        "school_name": session.school_name,
                        "sessions": opts["sessions"],
                        "classes": opts["classes"]
                    }

                # If failed: extract error text from dialog or DOM validation labels
                error_reason = ""
                if dialog_messages:
                    error_reason = " | ".join(dialog_messages)
                else:
                    err_text = page.evaluate("""
                    () => {
                        const msgs = [];
                        const els = document.querySelectorAll('.validationheader, .alert, .text-danger, [id*="ValidationSummary"], span[style*="red" i]');
                        els.forEach(el => {
                            const t = (el.innerText || '').trim();
                            if (t && t.length < 200 && !t.includes('Copyright') && !t.includes('Visitor') && !t.includes('ऑनलाइन यूजर') && !t.includes('भाषा') && !t.includes('फ़ॉन्ट')) {
                                msgs.push(t);
                            }
                        });
                        return msgs.join('; ');
                    }
                    """)
                    if err_text:
                        error_reason = err_text

                if not error_reason:
                    error_reason = "कृपया सही पासवर्ड अथवा कैप्चा दर्ज करें !"

                # Refresh captcha for next attempt
                try:
                    page.evaluate("() => { if (typeof reload === 'function') reload(); }")
                    time.sleep(1.0)
                except Exception:
                    try:
                        page.goto(LOGIN_URL, timeout=30000, wait_until="domcontentloaded")
                        time.sleep(1.0)
                    except Exception:
                        pass
                new_cap = self._extract_captcha(page)

                return {
                    "success": False,
                    "error": error_reason,
                    "captcha_b64": new_cap
                }
            finally:
                try:
                    page.remove_listener("dialog", _handle_dialog)
                except Exception:
                    pass

        return self._execute(_task, timeout=45.0)

    def fetch_students(self, session_id: str, session_val: str, class_val: str, deep_scrape: bool = False) -> Dict[str, Any]:
        """Submits session & class on the portal and scrapes the student records table."""
        def _task():
            session = self._get_session(session_id)
            if not session:
                return {"success": False, "error": "Invalid or expired session ID."}

            session.touch()
            page = session.page

            # Ensure we are on the profile page
            if "PSP_UpdateStudentProfileDataEntry.aspx" not in page.url:
                page.goto(PROFILE_URL, timeout=45000, wait_until="domcontentloaded")
                time.sleep(1.2)

            # Step 1: Select Session and settle any ASP.NET autopostback
            session_changed = page.evaluate("""(val) => {
                if (!val) return false;
                const selects = Array.from(document.querySelectorAll('select'));
                let sessionSel = selects.find(s => {
                    const id = (s.id || '').toLowerCase();
                    const name = (s.name || '').toLowerCase();
                    const hasYear = Array.from(s.options).some(o => /20[123]\\d/i.test(o.text));
                    return id.includes('session') || name.includes('session') || hasYear;
                }) || selects[0];

                if (sessionSel && sessionSel.value !== val) {
                    sessionSel.value = val;
                    sessionSel.dispatchEvent(new Event('change', { bubbles: true }));
                    return true;
                }
                return false;
            }""", session_val)

            if session_changed:
                try:
                    page.wait_for_load_state("domcontentloaded", timeout=8000)
                    time.sleep(1.2)
                except Exception:
                    time.sleep(1.5)

            # Step 2: Select Class and settle any autopostback
            class_changed = page.evaluate("""(val) => {
                if (!val) return false;
                const selects = Array.from(document.querySelectorAll('select'));
                let classSel = selects.find(s => {
                    const id = (s.id || '').toLowerCase();
                    const name = (s.name || '').toLowerCase();
                    const hasClass = Array.from(s.options).some(o => /class|कक्षा/i.test(o.text));
                    return id.includes('class') || name.includes('class') || hasClass;
                }) || (selects.length > 1 ? selects[1] : null);

                if (classSel && classSel.value !== val) {
                    classSel.value = val;
                    classSel.dispatchEvent(new Event('change', { bubbles: true }));
                    return true;
                }
                return false;
            }""", class_val)

            if class_changed:
                try:
                    page.wait_for_load_state("domcontentloaded", timeout=8000)
                    time.sleep(1.0)
                except Exception:
                    time.sleep(1.2)

            # Step 3: Click View / Submit Button
            res = page.evaluate("""() => {
                const buttons = Array.from(document.querySelectorAll('input[type="submit"], input[type="button"], button'));
                let submitBtn = null;
                for (const b of buttons) {
                    const val = (b.value || b.innerText || b.id || b.name || '').toLowerCase();
                    if (/देखें|show|view|search|get|खोजें|submit/i.test(val)) {
                        submitBtn = b;
                        break;
                    }
                }
                if (!submitBtn && buttons.length > 0) submitBtn = buttons[0];

                if (submitBtn) {
                    submitBtn.click();
                    return { clicked: true };
                }
                return { clicked: false, reason: "No view/submit button found near dropdowns." };
            }""")

            if not res.get("clicked"):
                return {"success": False, "error": res.get("reason", "Submit button not found.")}

            # Settle postback
            page.wait_for_timeout(1500)

            # Step 4: Dynamically poll for student GridView table rendering
            start_poll = time.time()
            while time.time() - start_poll < 20.0:
                table_res = self._extract_student_table(page)
                if table_res.get("success") and table_res.get("count", 0) > 0:
                    return table_res

                # Check if explicit portal notice appeared (e.g. no records)
                has_notice = page.evaluate("""() => {
                    const el = document.querySelector('[id*="lblMsg"], [id*="lblMessage"], .alert, .text-danger, span[style*="red" i]');
                    return el ? (el.innerText || '').trim() : '';
                }""")
                if has_notice and any(w in has_notice.lower() for w in ["रिकॉर्ड", "record", "not found", "उपलब्ध नहीं", "कोई रिकॉर्ड नहीं"]):
                    return table_res

                page.wait_for_timeout(500)

            return self._extract_student_table(page)

        return self._execute(_task, timeout=50.0)

    def automated_fetch(self, school_code: str, password: str, session_val: str, class_val: str) -> Dict[str, Any]:
        """
        Enterprise-tier headless sync:
        Creates an ephemeral context, auto-solves the CAPTCHA via local OCR, logs in,
        and extracts student records in one call.
        """
        def _task():
            context = self.browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            )
            page = context.new_page()
            dialog_messages = []
            def _handle_dialog(dialog):
                dialog_messages.append(dialog.message)
                try:
                    dialog.accept()
                except Exception:
                    pass

            page.on("dialog", _handle_dialog)

            try:
                page.goto(LOGIN_URL, timeout=45000, wait_until="domcontentloaded")
                time.sleep(1.0)

                # Attempt login with up to 3 OCR retries
                max_attempts = 3
                logged_in = False
                for attempt in range(max_attempts):
                    dialog_messages.clear()
                    captcha_b64 = self._extract_captcha(page)
                    solved_code = solve_captcha_from_base64(captcha_b64)

                    page.fill("#txtUNameschool", school_code)
                    page.evaluate("() => document.getElementById('txtUNameschool').dispatchEvent(new Event('change', { bubbles: true }))")
                    page.wait_for_timeout(600)

                    # Inject salted SHA512
                    page.evaluate("""(args) => {
                        const pwdEl = document.getElementById('txtUPswdschool');
                        if (pwdEl) { pwdEl.onblur = null; pwdEl.removeAttribute('onblur'); }
                        const capEl = document.getElementById('txtschool_Captcha');
                        if (capEl) capEl.value = args.captcha;
                        const u = document.getElementById('hdnUserIdschool')?.value || args.username.trim();
                        const rand = document.getElementById('hdnRandNu512')?.value || '';
                        if (typeof SHA512 === 'function') {
                            const pSha = SHA512(args.password);
                            const hdnDempps = document.getElementById('hdnDempps');
                            if (hdnDempps) hdnDempps.value = pSha;
                            const hdnDemppsSha512 = document.getElementById('hdnDemppsSha512');
                            if (hdnDemppsSha512) hdnDemppsSha512.value = pSha;
                            const sha = SHA512(u.toLowerCase() + args.password);
                            const hashs = SHA512(rand + sha);
                            if (pwdEl) pwdEl.value = hashs;
                        }
                    }""", {"password": password, "captcha": solved_code, "username": school_code})

                    btn = page.query_selector("#btnloginschool")
                    if btn:
                        btn.click()
                    else:
                        page.keyboard.press("Enter")

                    start_w = time.time()
                    while time.time() - start_w < 6.0:
                        if dialog_messages or "schoollogin.aspx" not in (page.url or "").lower():
                            break
                        page.wait_for_timeout(250)

                    if "schoollogin.aspx" not in (page.url or "").lower():
                        logged_in = True
                        break

                    # Refresh captcha for retry
                    try:
                        page.evaluate("() => { if (typeof reload === 'function') reload(); }")
                        time.sleep(1.0)
                    except Exception:
                        page.reload(wait_until="domcontentloaded")
                        time.sleep(1.0)

                if not logged_in:
                    err_msg = " | ".join(dialog_messages) if dialog_messages else "Automated OCR authentication failed after multiple attempts."
                    return {"success": False, "error": err_msg}

                # Navigate to profile entry page
                if "PSP_UpdateStudentProfileDataEntry.aspx" not in page.url:
                    page.goto(PROFILE_URL, timeout=45000, wait_until="domcontentloaded")
                    time.sleep(1.5)

                # Select Session & Class using same postback handling
                fake_session_id = "ephemeral"
                fake_s = BrowserSession(fake_session_id, context, page)
                with self.sessions_lock:
                    self.sessions[fake_session_id] = fake_s
                try:
                    table_data = self.fetch_students(fake_session_id, session_val, class_val)
                    return table_data
                finally:
                    with self.sessions_lock:
                        self.sessions.pop(fake_session_id, None)

            finally:
                try:
                    page.remove_listener("dialog", _handle_dialog)
                except Exception:
                    pass
                try:
                    page.close()
                    context.close()
                except Exception:
                    pass

        return self._execute(_task, timeout=90.0)

    def close_session(self, session_id: str) -> bool:
        """Closes and releases a user session context."""
        def _task():
            with self.sessions_lock:
                s = self.sessions.pop(session_id, None)
            if s:
                s.close()
                return True
            return False

        return self._execute(_task, timeout=10.0)

    # =========================================================================
    # INTERNAL HELPERS
    # =========================================================================

    def _get_session(self, session_id: str) -> Optional[BrowserSession]:
        with self.sessions_lock:
            return self.sessions.get(session_id)

    def _extract_captcha(self, page: Page) -> str:
        try:
            elem = page.query_selector("#captchimg, img[src*='CaptchaImg' i], img[src*='captcha' i]")
            if not elem:
                elem = page.evaluate_handle("""
                () => {
                    const inp = document.getElementById('txtschool_Captcha');
                    if (inp) {
                        const tr = inp.closest('tr, td, .form-group, div');
                        if (tr) return tr.querySelector('img');
                    }
                    return null;
                }
                """).as_element()
            if elem:
                png_bytes = elem.screenshot()
                return f"data:image/png;base64,{base64.b64encode(png_bytes).decode('ascii')}"
        except Exception:
            pass
        return ""

    def _extract_school_name(self, page: Page) -> str:
        """Extracts cleaned school name from portal DOM header/labels."""
        try:
            name = page.evaluate("""() => {
                const ids = ['#lblSchoolName', '#ctl00_lblSchoolName', '#lblSchool', '#lblUser', '[id*="lblSchoolName" i]', '.schoolname'];
                for (const sel of ids) {
                    const el = document.querySelector(sel);
                    if (el) {
                        const txt = (el.innerText || '').replace(/^(welcome|स्वागत)\\s*[-:]*\\s*/i, '').trim();
                        if (txt && txt.length > 2) return txt.split('\\n')[0].trim();
                    }
                }
                const header = document.querySelector('header, .header, nav');
                if (header) {
                    const nodes = Array.from(header.querySelectorAll('span, b, strong, h2, h3'));
                    for (const n of nodes) {
                        const t = (n.innerText || '').trim();
                        if (/(school|academy|vidyalaya|विद्यालय|शिक्षा|public)/i.test(t) && !t.includes('RajPSP')) {
                            return t;
                        }
                    }
                }
                return '';
            }""")
            return (name or "").strip()
        except Exception:
            return ""

    def _scrape_dropdowns(self, page: Page) -> Dict[str, Any]:
        """Scrapes Session and Class options from the portal."""
        result = {"sessions": [], "classes": []}
        try:
            sessions_data = page.evaluate("""
            () => {
                const el = document.querySelector("select[id*='Session' i], select[name*='Session' i]");
                if (!el) return [];
                return Array.from(el.options)
                    .filter(o => o.value && o.value.trim() !== "" && !o.text.includes("Select"))
                    .map(o => ({ value: o.value.trim(), text: o.text.trim() }));
            }
            """)
            result["sessions"] = sessions_data or []

            classes_data = page.evaluate("""
            () => {
                const el = document.querySelector("select[id*='Class' i], select[name*='Class' i]");
                if (!el) return [];
                return Array.from(el.options)
                    .filter(o => o.value && o.value.trim() !== "" && !o.text.includes("Select"))
                    .map(o => ({ value: o.value.trim(), text: o.text.trim() }));
            }
            """)
            result["classes"] = classes_data or []
        except Exception:
            pass
        return result

    def _extract_student_table(self, page: Page) -> Dict[str, Any]:
        """Extracts headers and rows from the student GridView table, filtering out navigation menus."""
        try:
            table_info = page.evaluate("""
            () => {
                const tables = Array.from(document.querySelectorAll("table"));
                if (tables.length === 0) return { found: false, count: 0 };

                const menuKeywords = [
                    'कर्मचारी', 'मान्यता', 'बोर्ड एग्जाम', 'बालिका फीस', 'विविध',
                    'परीक्षा परिणाम', 'फीस सूचना', 'आरटीई प्रवेश', 'लॉगआउट', 'logout',
                    'पासवर्ड बदलें', 'change password', 'विद्यालय प्रोफाइल'
                ];

                let bestTable = null;
                let bestScore = 0;

                tables.forEach(tbl => {
                    if (tbl.closest('nav, .navbar, .menu, #menu, .sidebar, #sidebar, header')) return;
                    const text = (tbl.innerText || '').toLowerCase();
                    let menuCount = 0;
                    for (const mk of menuKeywords) {
                        if (text.includes(mk.toLowerCase())) menuCount++;
                    }
                    if (menuCount >= 2) return;

                    const rows = Array.from(tbl.querySelectorAll("tr"));
                    if (rows.length < 2) return;

                    let headerCells = Array.from(rows[0].querySelectorAll("th, td"));
                    if (headerCells.length <= 1 && rows.length > 2) {
                        headerCells = Array.from(rows[1].querySelectorAll("th, td"));
                    }
                    const headers = headerCells.map(h => (h.innerText || '').trim().replace(/\\s+/g, ' '));
                    if (headers.length < 4) return;

                    const joined = headers.join(' ').toLowerCase();
                    const hasStudent = ['नाम', 'name', 'विद्यार्थी', 'छात्र', 'student'].some(k => joined.includes(k));
                    const hasAux = ['पिता', 'father', 'माता', 'mother', 'dob', 'जन्म', 'scholar', 'प्रवेशांक', 'लिंग', 'gender', 'क्रमांक', 'sr'].some(k => joined.includes(k));

                    if (!hasStudent || !hasAux) return;

                    let score = 10 + headers.length + rows.length;
                    if (score > bestScore) {
                        bestScore = score;
                        bestTable = { tbl, headers, rows };
                    }
                });

                if (!bestTable) return { found: false, count: 0 };

                const parsedRows = [];
                const dataStart = bestTable.rows[0].querySelectorAll('th').length > 0 ? 1 : (bestTable.rows.length > 2 && bestTable.rows[1].querySelectorAll('th').length > 0 ? 2 : 1);

                for (let i = dataStart; i < bestTable.rows.length; i++) {
                    const tr = bestTable.rows[i];
                    const cells = Array.from(tr.querySelectorAll("td"));
                    if (cells.length === 0) continue;
                    const tText = (tr.innerText || '').trim();
                    if (/page \\d+ of|total record|first|previous|next|last/i.test(tText) && cells.length <= 2) continue;
                    parsedRows.push(cells.map(c => (c.innerText || '').trim().replace(/\\s+/g, ' ')));
                }

                return {
                    found: parsedRows.length > 0,
                    headers: bestTable.headers,
                    rows: parsedRows,
                    count: parsedRows.length
                };
            }
            """)
            if table_info and table_info.get("found"):
                return {
                    "success": True,
                    "headers": table_info.get("headers", []),
                    "rows": table_info.get("rows", []),
                    "count": table_info.get("count", 0),
                    "message": f"Successfully extracted {table_info.get('count', 0)} student records."
                }
            else:
                return {
                    "success": True,
                    "headers": [],
                    "rows": [],
                    "count": 0,
                    "message": "No student records found for the selected Session and Class on the portal."
                }
        except Exception as e:
            return {"success": False, "error": f"DOM parsing error: {e}"}


# Global singleton instance
browser_pool = BrowserContextPool()
