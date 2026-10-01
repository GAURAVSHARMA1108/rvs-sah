"""
Browser Manager Module for RajPSP Student Profile Scraper
Automates Rajasthan Private School Portal in background headless Chromium.
Features:
- In-Dashboard Portal Login: fetches live CAPTCHA image, injects credentials,
  handles ASP.NET postback & client-side SHA512 hashing, and captures exact portal feedback.
- Navigates to PSP_UpdateStudentProfileDataEntry.aspx upon login.
- Scrapes real Session and Class options dynamically from live portal DOM.
- Submits Session/Class and extracts real student GridView table.
- Deep scrapes full student profile form fields on demand.
- Strictly ZERO mock data.
"""

import re
import time
import base64
import queue
import threading
import concurrent.futures
from typing import Dict, List, Any, Optional, Callable
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page


LOGIN_URL = "https://rajpsp.rajasthan.gov.in/home/schoollogin.aspx"
PROFILE_URL = "https://rajpsp.rajasthan.gov.in/School/PSP_UpdateStudentProfileDataEntry.aspx"


class BrowserManager:
    """Thread-safe background Playwright Browser Controller."""

    def __init__(self, log_callback: Optional[Callable[[str, str, str], None]] = None):
        self.log_callback = log_callback or self._default_logger
        self.task_queue = queue.Queue()
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True, name="PlaywrightWorker")
        self.worker_thread.start()

        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.is_running = False
        self.login_detected = False
        self.current_url = ""
        self.school_user = ""
        self.school_name = ""
        self.cached_headers: List[str] = []
        self.cached_rows: List[List[str]] = []
        self.cached_row_actions: List[Dict[str, Any]] = []

    def _default_logger(self, level: str, message: str, reason: str):
        timestamp = time.strftime("%H:%M:%S")
        print(f"[{timestamp}] [{level.upper()}] {message} | Reason: {reason}")

    def log(self, level: str, message: str, reason: str):
        self.log_callback(level, message, reason)

    def _worker_loop(self):
        with sync_playwright() as p:
            self.playwright = p
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

            self._cleanup_resources()

    def _execute(self, fn: Callable, timeout: float = 60.0) -> Any:
        future = concurrent.futures.Future()
        self.task_queue.put((fn, future))
        try:
            return future.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            self.log("ERROR", "Operation timed out on browser worker thread.", f"Timeout ({timeout}s) exceeded.")
            return {"success": False, "message": "Browser operation timed out.", "reason": "Worker timeout"}
        except Exception as e:
            self.log("ERROR", f"Browser error: {str(e)}", f"Exception on worker: {type(e).__name__}")
            return {"success": False, "message": str(e), "reason": type(e).__name__}

    def _cleanup_resources(self):
        try:
            if self.context:
                self.context.close()
            if self.browser:
                self.browser.close()
        except Exception:
            pass
        finally:
            self.is_running = False
            self.login_detected = False
            self.context = None
            self.browser = None
            self.page = None

    def _ensure_browser(self):
        """Ensures background Chromium page is initialized and open."""
        if not self.is_running or not self.page or self.page.is_closed():
            self.log("ACTION", "Starting background Chromium automation engine...", "Initializing headless browser.")
            self.browser = self.playwright.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
            )
            self.context = self.browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            )
            self.page = self.context.new_page()
            self.is_running = True
            self.login_detected = False

    def _capture_captcha_b64(self) -> str:
        """Finds and captures screenshot of the live captcha image on the page."""
        try:
            # First try #captchimg
            captcha_elem = self.page.query_selector("#captchimg, img[src*='CaptchaImg' i], img[src*='captcha' i]")
            if not captcha_elem:
                # Search by proximity to txtschool_Captcha
                captcha_elem = self.page.evaluate_handle("""
                () => {
                    const inp = document.getElementById('txtschool_Captcha');
                    if (inp) {
                        const tr = inp.closest('tr, td, .form-group, div');
                        if (tr) return tr.querySelector('img');
                    }
                    return null;
                }
                """).as_element()

            if captcha_elem:
                png_bytes = captcha_elem.screenshot()
                return f"data:image/png;base64,{base64.b64encode(png_bytes).decode('ascii')}"
        except Exception as e:
            self.log("WARNING", f"Could not capture captcha screenshot: {e}", "Retrying or element not rendered.")
        return ""

    # =========================================================================
    # IN-DASHBOARD AUTHENTICATION METHODS
    # =========================================================================

    def init_login_session(self) -> Dict[str, Any]:
        """
        Loads the portal login page in the background and extracts the live CAPTCHA image.
        """
        def _task():
            self._ensure_browser()
            self.log("ACTION", f"Navigating background browser to {LOGIN_URL}...", "Loading portal login form.")
            self.page.goto(LOGIN_URL, timeout=45000, wait_until="domcontentloaded")
            self.current_url = self.page.url

            # Wait briefly for captcha image to render
            time.sleep(1.0)
            captcha_b64 = self._capture_captcha_b64()

            if captcha_b64:
                self.log(
                    "SUCCESS",
                    "Loaded portal login page & captured live CAPTCHA.",
                    "Live captcha image fetched from Rajasthan PSP server. Ready for credentials."
                )
                return {
                    "success": True,
                    "captcha_b64": captcha_b64,
                    "current_url": self.current_url,
                    "message": "Login page loaded with live Captcha."
                }
            else:
                self.log("WARNING", "Loaded login page but could not find Captcha element.", "Page DOM structure check.")
                return {
                    "success": True,
                    "captcha_b64": "",
                    "current_url": self.current_url,
                    "message": "Loaded login page. Captcha image not found."
                }

        return self._execute(_task, timeout=75.0)

    def refresh_captcha(self) -> Dict[str, Any]:
        """Refreshes the CAPTCHA image on the portal login page without full reload."""
        def _task():
            self._ensure_browser()
            self.log("ACTION", "Refreshing CAPTCHA on portal login page...", "User requested new captcha.")

            # Trigger portal's reload() function or reload image source directly
            try:
                self.page.evaluate("""() => {
                    if (typeof reload === 'function') {
                        reload();
                    } else {
                        const img = document.getElementById('captchimg');
                        if (img) img.src = '../Home/CaptchaImg.aspx?refresh=' + Math.random();
                    }
                }""")
                time.sleep(1.0)
            except Exception:
                # Fallback to navigating to LOGIN_URL if page not initialized
                self.page.goto(LOGIN_URL, timeout=30000, wait_until="domcontentloaded")
                time.sleep(1.0)

            captcha_b64 = self._capture_captcha_b64()
            self.log("SUCCESS", "Fetched fresh live CAPTCHA.", "Live Captcha image updated.")
            return {"success": True, "captcha_b64": captcha_b64}

        return self._execute(_task, timeout=35.0)

    def check_school_code(self, username: str) -> Dict[str, Any]:
        """
        Pre-resolves School PSP Code to internal UserID on blur in the UI.
        """
        def _task():
            self._ensure_browser()
            current_url = (self.page.url or "").lower()
            if "schoollogin.aspx" not in current_url:
                self.page.goto(LOGIN_URL, timeout=35000, wait_until="domcontentloaded")
                time.sleep(1.0)

            clean_user = username.strip()
            if not clean_user:
                return {"valid": False, "message": "Empty school code."}

            dialog_messages = []
            def _handle_dialog(dialog):
                dialog_messages.append(dialog.message)
                try:
                    dialog.accept()
                except Exception:
                    pass

            self.page.on("dialog", _handle_dialog)
            try:
                self.page.fill("#txtUNameschool", clean_user)
                self.page.evaluate("() => document.getElementById('txtUNameschool').dispatchEvent(new Event('change', { bubbles: true }))")

                start_res = time.time()
                while time.time() - start_res < 5.0:
                    if dialog_messages:
                        break
                    uid = self.page.evaluate("() => document.getElementById('hdnUserIdschool')?.value")
                    if uid:
                        break
                    self.page.wait_for_timeout(200)

                if dialog_messages:
                    err = " | ".join(dialog_messages)
                    return {"valid": False, "error": err, "message": err}

                uid = self.page.evaluate("() => document.getElementById('hdnUserIdschool')?.value")
                role = self.page.evaluate("() => document.getElementById('hdnSchoolType_RoleCode')?.value")
                if uid:
                    return {"valid": True, "school_id": uid, "role_code": role}
                return {"valid": False, "error": "Could not verify school code."}
            finally:
                try:
                    self.page.remove_listener("dialog", _handle_dialog)
                except Exception:
                    pass

        return self._execute(_task, timeout=15.0)

    def submit_login(self, username: str, password: str, captcha: str) -> Dict[str, Any]:
        """
        Resolves School PSP Code to internal portal School ID, computes salted SHA-512 hashing,
        clicks login, and captures exact portal feedback (success or website alert dialog).
        """
        def _task():
            self._ensure_browser()

            current_url = (self.page.url or "").lower()
            if "schoollogin.aspx" not in current_url:
                self.log("ACTION", f"Navigating to {LOGIN_URL}...", "Reloading login form.")
                self.page.goto(LOGIN_URL, timeout=35000, wait_until="domcontentloaded")
                time.sleep(1.0)

            clean_user = username.strip()
            clean_pwd = password.strip()
            clean_captcha = captcha.strip()

            self.log(
                "ACTION",
                f"Processing credentials for School PSP Code: '{clean_user}'...",
                "Resolving school ID and preparing SHA-512 authentication hash."
            )

            # Capture alerts / dialogs from actual website
            dialog_messages = []
            def _handle_dialog(dialog):
                self.log("INFO", f"Portal dialog message: '{dialog.message}'", f"Alert type: {dialog.type}")
                dialog_messages.append(dialog.message)
                try:
                    dialog.accept()
                except Exception:
                    pass

            self.page.on("dialog", _handle_dialog)

            try:
                # 1. Ensure School PSP Code is resolved to internal School UserID and Role
                current_uname = self.page.evaluate("() => document.getElementById('txtUNameschool')?.value")
                current_uid = self.page.evaluate("() => document.getElementById('hdnUserIdschool')?.value")

                if current_uname != clean_user or not current_uid:
                    self.log(
                        "ACTION",
                        f"Resolving School PSP Code '{clean_user}' on Rajasthan portal...",
                        "Querying portal database for school user ID and role."
                    )
                    self.page.fill("#txtUNameschool", clean_user)
                    self.page.evaluate("() => document.getElementById('txtUNameschool').dispatchEvent(new Event('change', { bubbles: true }))")

                    # Wait for hdnUserIdschool to be populated or an alert dialog
                    start_res = time.time()
                    while time.time() - start_res < 6.0:
                        if dialog_messages:
                            break
                        uid = self.page.evaluate("() => document.getElementById('hdnUserIdschool')?.value")
                        if uid:
                            break
                        self.page.wait_for_timeout(250)

                    if dialog_messages:
                        err_msg = " | ".join(dialog_messages)
                        self.log("ERROR", f"School PSP Code rejected: {err_msg}", f"Portal alert: {err_msg}")
                        return {
                            "success": False,
                            "error": err_msg,
                            "captcha_b64": self._capture_captcha_b64(),
                            "current_url": self.page.url,
                            "reason": f"Actual website returned: {err_msg}"
                        }

                resolved_uid = self.page.evaluate("() => document.getElementById('hdnUserIdschool')?.value") or clean_user
                self.log("INFO", f"School PSP Code '{clean_user}' mapped to Portal School ID: '{resolved_uid}'.", "Hashing password with portal salt.")

                # 2. Inject password, compute exact single SHA-512 hash, and set captcha
                inject_res = self.page.evaluate("""(args) => {
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

                    // Exact single SHA-512 calculation
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

                # Clear dialogs list before final submit
                dialog_messages.clear()

                self.log(
                    "ACTION",
                    f"Submitting credentials for School ID '{resolved_uid}' (Hash len: {inject_res.get('pwdLen')})...",
                    "Clicking #btnloginschool."
                )

                # 3. Click login submit button
                self.page.click("#btnloginschool")

                # 3. Wait for either dialog alert or URL change or response
                start_wait = time.time()
                while time.time() - start_wait < 10.0:
                    if dialog_messages:
                        # Server immediately rejected with an alert dialog (e.g. wrong captcha or password)
                        break
                    url_now = (self.page.url or "").lower()
                    if "schoollogin.aspx" not in url_now:
                        # URL changed, authenticated session established!
                        break
                    self.page.wait_for_timeout(250)

                current_url = self.page.url
                url_lower = current_url.lower()

                # Check if login succeeded: URL left schoollogin.aspx and is not an error page
                if "schoollogin.aspx" not in url_lower and "error_page.aspx" not in url_lower:
                    self.login_detected = True
                    self.school_user = clean_user
                    self.log(
                        "SUCCESS",
                        f"Login successful for School {clean_user}!",
                        f"Portal authenticated session. Current URL: {current_url}"
                    )

                    # Redirect to target PSP_UpdateStudentProfileDataEntry.aspx
                    self.log(
                        "ACTION",
                        f"Navigating to {PROFILE_URL}...",
                        "Transitioning to Student Profile Data Entry page."
                    )
                    self.page.goto(PROFILE_URL, timeout=45000, wait_until="domcontentloaded")
                    self.current_url = self.page.url

                    # Scrape school name from portal page
                    school_name = self._extract_school_name_internal()
                    if school_name:
                        self.school_name = school_name

                    # Automatically scrape real Session and Class options
                    time.sleep(1.0)
                    dropdown_data = self._scrape_dropdowns_internal()

                    return {
                        "success": True,
                        "message": f"Successfully logged in as School {clean_user}!",
                        "current_url": self.current_url,
                        "school_name": self.school_name or clean_user,
                        "sessions": dropdown_data.get("sessions", []),
                        "classes": dropdown_data.get("classes", []),
                        "reason": f"Portal redirected to {self.current_url} and loaded dropdowns."
                    }

                # If login failed: capture exact error message from actual website
                error_reason = ""
                if dialog_messages:
                    error_reason = " | ".join(dialog_messages)
                else:
                    # Check DOM labels for genuine error text (ignoring normal page header/footer labels)
                    err_text = self.page.evaluate("""
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
                    if "error_page.aspx" in url_lower:
                        error_reason = "Server rejected request (Session error or server exception)."
                    else:
                        error_reason = "Invalid credentials or rejected by Rajasthan PSP server."

                self.log(
                    "ERROR",
                    f"Portal Login Failed: {error_reason}",
                    f"Actual website feedback: '{error_reason}'. URL: {current_url}"
                )

                # Refresh captcha for next attempt using reload()
                try:
                    self.page.evaluate("() => { if (typeof reload === 'function') reload(); }")
                    time.sleep(1.0)
                except Exception:
                    try:
                        self.page.goto(LOGIN_URL, timeout=30000, wait_until="domcontentloaded")
                        time.sleep(1.0)
                    except Exception:
                        pass
                new_captcha = self._capture_captcha_b64()

                return {
                    "success": False,
                    "error": error_reason,
                    "captcha_b64": new_captcha,
                    "current_url": self.page.url,
                    "reason": f"Actual website returned: {error_reason}"
                }

            finally:
                try:
                    self.page.remove_listener("dialog", _handle_dialog)
                except Exception:
                    pass

        return self._execute(_task, timeout=50.0)

    # =========================================================================
    # DROPDOWN SCRAPING (STRICTLY FROM LIVE PORTAL DOM)
    # =========================================================================

    def _scrape_dropdowns_internal(self) -> Dict[str, Any]:
        """Scrapes real dropdown options directly from PSP_UpdateStudentProfileDataEntry.aspx."""
        try:
            result = self.page.evaluate("""
            () => {
                const selects = Array.from(document.querySelectorAll('select'));
                let sessionSelect = null;
                let classSelect = null;
                const allSelects = [];

                selects.forEach((sel, idx) => {
                    const id = (sel.id || '').toLowerCase();
                    const name = (sel.name || '').toLowerCase();
                    const options = Array.from(sel.options).map(o => ({
                        value: o.value,
                        text: o.text.trim()
                    })).filter(o => o.text.length > 0);

                    const info = { id: sel.id, name: sel.name, index: idx, options: options };
                    allSelects.push(info);

                    const hasYear = options.some(o => /20[123]\\d/i.test(o.text) || /सत्र/i.test(o.text));
                    if (id.includes('session') || name.includes('session') || hasYear || /सत्र/i.test(id)) {
                        if (!sessionSelect) sessionSelect = info;
                    }

                    const hasClass = options.some(o => /class|कक्षा|1st|2nd|3rd|4th|5th|6th|7th|8th|9th|10th/i.test(o.text));
                    if (id.includes('class') || name.includes('class') || hasClass || /कक्षा/i.test(id)) {
                        if (!classSelect) classSelect = info;
                    }
                });

                if (!sessionSelect && allSelects.length > 0) sessionSelect = allSelects[0];
                if (!classSelect && allSelects.length > 1) classSelect = allSelects[1];

                return {
                    sessionSelect: sessionSelect,
                    classSelect: classSelect,
                    totalSelectsFound: allSelects.length,
                    pageTitle: document.title,
                    pageUrl: window.location.href
                };
            }
            """)

            sessions = result.get("sessionSelect", {}).get("options", []) if result.get("sessionSelect") else []
            classes = result.get("classSelect", {}).get("options", []) if result.get("classSelect") else []

            if sessions or classes:
                self.log(
                    "SUCCESS",
                    f"Scraped real options: {len(sessions)} Sessions, {len(classes)} Classes from live portal.",
                    f"Page: '{result.get('pageTitle', '')}'."
                )

            return {
                "success": bool(sessions or classes),
                "sessions": sessions,
                "classes": classes,
                "total_selects": result.get("totalSelectsFound", 0)
            }
        except Exception as e:
            self.log("ERROR", f"Failed to scrape dropdowns: {e}", f"Exception: {type(e).__name__}")
            return {"success": False, "sessions": [], "classes": [], "reason": str(e)}

    def get_session_and_class_options(self) -> Dict[str, Any]:
        """Public method to fetch Session & Class options."""
        def _task():
            self._ensure_browser()
            current_url = (self.page.url or "").lower()
            if "psp_updatestudentprofiledataentry" not in current_url:
                self.log(
                    "WARNING",
                    "Not on Profile Entry page.",
                    f"Current URL: {self.page.url}. Please complete portal login first."
                )
                return {
                    "success": False,
                    "sessions": [],
                    "classes": [],
                    "message": "Not on Profile Entry page.",
                    "reason": f"Active page is {self.page.url}. Please log in first."
                }
            return self._scrape_dropdowns_internal()

        return self._execute(_task, timeout=30.0)

    @staticmethod
    def _clean_school_name_text(raw: str) -> str:
        """Sanitizes raw scraped school name by removing Welcome prefixes and menu navigation links."""
        if not raw:
            return ""
        # 1. Take first line only
        s = raw.split("\n")[0].split("\r")[0].strip()
        # 2. Strip "Welcome -" or "Welcome:" or "स्वागत -"
        s = re.sub(r'^(?:welcome|स्वागत)\s*[-:]*\s*', '', s, flags=re.IGNORECASE).strip()
        # 3. Strip any menu links or trailing portal navigation options
        s = re.split(r'\s*(?:मुख्य पृष्ठ|स्कूल सम्पर्क विवरण|पासवर्ड बदलें|लॉगआउट|logout|change password|home)\b', s, flags=re.IGNORECASE)[0].strip()
        # 4. Remove trailing pipes, dashes, colons, spaces
        s = re.sub(r'[\s|\-:;]+$', '', s).strip()
        return s

    def _extract_school_name_internal(self) -> str:
        """Extracts verified school name directly from Rajasthan PSP portal DOM."""
        try:
            name = self.page.evaluate("""() => {
                const cleanText = (raw) => {
                    if (!raw) return '';
                    let s = raw.split(/[\\r\\n]+/)[0];
                    s = s.replace(/^(welcome|स्वागत)\\s*[-:]*\\s*/i, '');
                    const navWords = ['मुख्य पृष्ठ', 'स्कूल सम्पर्क विवरण', 'पासवर्ड बदलें', 'लॉगआउट', 'logout', 'change password', 'home', 'portal'];
                    for (const w of navWords) {
                        const idx = s.indexOf(w);
                        if (idx !== -1) s = s.substring(0, idx);
                    }
                    return s.replace(/[\\s|\\-:;]+$/, '').trim();
                };

                const ids = [
                    '#lblSchoolName',
                    '#ctl00_lblSchoolName',
                    '#ctl00_ContentPlaceHolder1_lblSchoolName',
                    '#lblSchool',
                    '#ctl00_lblSchool',
                    '#lblUser',
                    '#ctl00_lblUser',
                    '[id*="lblSchoolName" i]',
                    '[id*="SchoolName" i]',
                    '[id*="lblSchool" i]',
                    '.schoolname',
                    '.school-name'
                ];
                for (const selector of ids) {
                    const el = document.querySelector(selector);
                    if (el) {
                        const txt = cleanText((el.innerText || el.textContent || '').trim());
                        if (txt && txt.length > 2) {
                            return txt;
                        }
                    }
                }
                const header = document.querySelector('header, .header, #header, #ctl00_header, nav, .navbar');
                if (header) {
                    const nodes = Array.from(header.querySelectorAll('span, b, strong, h1, h2, h3, h4, div'));
                    for (const n of nodes) {
                        const t = cleanText((n.innerText || '').trim());
                        if (t.length > 4 && t.length < 150) {
                            if (/(school|academy|vidyalaya|विद्यालय|शिक्षा|संस्थान|public|sen\\.? sec)/i.test(t)) {
                                return t;
                            }
                        }
                    }
                }
                const topSpans = Array.from(document.querySelectorAll('span, b, strong, font'));
                for (const s of topSpans.slice(0, 50)) {
                    const t = cleanText((s.innerText || '').trim());
                    if (t.length > 5 && t.length < 120) {
                        if (/(school|academy|विद्यालय|public school)/i.test(t) && !t.includes('RajPSP') && !t.includes('Portal')) {
                            return t;
                        }
                    }
                }
                return '';
            }""")
            if name:
                cleaned = self._clean_school_name_text(name)
                if cleaned:
                    self.school_name = cleaned
                    self.log("INFO", f"Identified School Name from portal: '{self.school_name}'", "Scraped from page header.")
                    return self.school_name
        except Exception as e:
            self.log("WARNING", f"Could not scrape school name: {e}", "Exception during school name extraction.")
        return self.school_name or ""

    # =========================================================================
    # REAL PORTAL FORM SUBMISSION & GRIDVIEW SCRAPING
    # =========================================================================

    def submit_session_and_class(self, session_val: str, class_val: str) -> Dict[str, Any]:
        """Submits Session & Class on portal, waits for postback, and scrapes real student GridView."""
        def _task():
            self._ensure_browser()
            current_url = (self.page.url or "").lower()

            if "psp_updatestudentprofiledataentry" not in current_url:
                return {
                    "success": False,
                    "found": False,
                    "message": "Not on Profile Entry page.",
                    "reason": "You must log in to the portal first."
                }

            self.log(
                "ACTION",
                f"Selecting Session='{session_val}' and Class='{class_val}' on portal...",
                "Submitting real form values to Rajasthan PSP server."
            )

            # Step 1: Select Session and settle any ASP.NET autopostback
            session_changed = self.page.evaluate("""(val) => {
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
                self.log("ACTION", "Session dropdown updated. Waiting for portal postback to settle...", "ASP.NET autopostback settling.")
                try:
                    self.page.wait_for_load_state("domcontentloaded", timeout=8000)
                    time.sleep(1.2)
                except Exception:
                    time.sleep(1.5)

            # Step 2: Select Class and settle any autopostback
            class_changed = self.page.evaluate("""(val) => {
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
                self.log("ACTION", "Class dropdown updated. Settle postback...", "Class selection updated.")
                try:
                    self.page.wait_for_load_state("domcontentloaded", timeout=8000)
                    time.sleep(1.0)
                except Exception:
                    time.sleep(1.2)

            # Step 3: Click View / Submit Button
            res = self.page.evaluate("""() => {
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
                    return { clicked: true, button: submitBtn.value || submitBtn.innerText || submitBtn.id };
                }

                return { clicked: false, reason: "No view/submit button found near dropdowns." };
            }""")

            if not res.get("clicked"):
                self.log("WARNING", "Submit button not found on portal page.", res.get("reason", ""))
                return {"success": False, "found": False, "message": res.get("reason")}

            self.log("ACTION", f"Clicked portal search button: '{res.get('button')}'.", "Polling for student GridView rendering...")

            # Give ASP.NET postback 1.5 seconds to start and invalidate old DOM
            self.page.wait_for_timeout(1500)

            # Step 4: Dynamically poll for table rendering (resolves 1st click requirement)
            start_poll = time.time()
            while time.time() - start_poll < 20.0:
                table_res = self._detect_table_internal()
                if table_res.get("found") and table_res.get("total_rows", 0) > 0:
                    self.log("SUCCESS", f"Extracted {table_res.get('total_rows')} student records on first fetch!", "GridView loaded.")
                    return table_res

                # Check if explicit portal notice appeared (e.g. no records for class)
                has_notice = self.page.evaluate("""() => {
                    const el = document.querySelector('[id*="lblMsg"], [id*="lblMessage"], .alert, .text-danger, span[style*="red" i]');
                    return el ? (el.innerText || '').trim() : '';
                }""")
                if has_notice and any(w in has_notice.lower() for w in ["रिकॉर्ड", "record", "not found", "उपलब्ध नहीं", "कोई रिकॉर्ड नहीं"]):
                    self.log("INFO", f"Portal returned notice: {has_notice}", "Zero records available.")
                    return table_res

                self.page.wait_for_timeout(600)

            return self._detect_table_internal()

        return self._execute(_task, timeout=50.0)

    def detect_student_table(self) -> Dict[str, Any]:
        """Scans page DOM for student GridView table."""
        def _task():
            self._ensure_browser()
            return self._detect_table_internal()

        return self._execute(_task, timeout=30.0)

    def _detect_table_internal(self) -> Dict[str, Any]:
        """Internal helper to scan and extract real student rows."""
        current_url = (self.page.url or "").lower()

        if "psp_updatestudentprofiledataentry" not in current_url:
            self.log("WARNING", "Not on Profile Entry page.", f"Active page: {self.page.url}.")
            return {
                "success": False,
                "found": False,
                "headers": [],
                "rows": [],
                "total_rows": 0,
                "message": "Not on Student Profile Data Entry page.",
                "reason": f"Active page is {self.page.url}. Please complete portal login first."
            }

        self.log("ACTION", "Scanning portal DOM for student records table...", "Evaluating real GridView elements.")

        data = self.page.evaluate("""
        () => {
            const tables = Array.from(document.querySelectorAll('table'));
            if (tables.length === 0) {
                const lblMsg = document.querySelector('[id*="lblMsg"], [id*="lblMessage"], .alert, .text-danger');
                const msgText = lblMsg ? lblMsg.innerText.trim() : "";
                return {
                    found: false,
                    tableCount: 0,
                    portalMessage: msgText,
                    reason: msgText ? ("Portal notice: " + msgText) : "No <table> elements exist on page."
                };
            }

            // Strictly blacklisted menu keywords that distinguish portal nav from student data
            const menuKeywords = [
                'कर्मचारी', 'मान्यता', 'बोर्ड एग्जाम', 'बालिका फीस', 'विविध',
                'परीक्षा परिणाम', 'फीस सूचना', 'आरटीई प्रवेश', 'लॉगआउट', 'logout',
                'पासवर्ड बदलें', 'change password', 'विद्यालय प्रोफाइल'
            ];

            let bestTable = null;
            let bestScore = 0;

            tables.forEach((tbl, tblIdx) => {
                // Reject tables inside nav / menu / header elements
                if (tbl.closest('nav, .navbar, .menu, #menu, .sidebar, #sidebar, .header, header')) {
                    return;
                }

                const tblText = (tbl.innerText || '').toLowerCase();
                let menuMatchCount = 0;
                for (const mk of menuKeywords) {
                    if (tblText.includes(mk.toLowerCase())) {
                        menuMatchCount++;
                    }
                }
                // If table contains 2 or more menu terms, it is definitely a navigation/menu table!
                if (menuMatchCount >= 2) {
                    return;
                }

                const rows = Array.from(tbl.querySelectorAll('tr'));
                if (rows.length < 2) return;

                let headerCells = Array.from(rows[0].querySelectorAll('th, td'));
                if (headerCells.length <= 1 && rows.length > 2) {
                    headerCells = Array.from(rows[1].querySelectorAll('th, td'));
                }

                const headers = headerCells.map(c => c.innerText.trim().replace(/\\s+/g, ' '));
                if (headers.length < 4) return; // Student GridView always has at least 4 columns

                const headersJoined = headers.join(' ').toLowerCase();

                // MUST have student name / विद्यार्थी / छात्र
                const hasStudentName = ['नाम', 'name', 'विद्यार्थी', 'छात्र', 'student'].some(k => headersJoined.includes(k));

                // MUST have at least one auxiliary student attribute
                const hasStudentAux = ['पिता', 'father', 'माता', 'mother', 'dob', 'जन्म', 'scholar', 'प्रवेशांक', 'लिंग', 'gender', 'क्रमांक', 's.no', 'sr', 'roll'].some(k => headersJoined.includes(k));

                if (!hasStudentName || !hasStudentAux) {
                    return;
                }

                let score = 10;
                const studentKeywords = [
                    's.no', 'sr', 'scholar', 'student', 'विद्यार्थी', 'छात्र', 'नाम', 'name',
                    'पिता', 'father', 'माता', 'mother', 'dob', 'जन्म', 'लिंग', 'gender',
                    'कक्षा', 'class', 'action', 'update', 'edit', 'entry', 'प्रविष्टि', 'एक्शन', 'profile', 'प्रवेशांक'
                ];
                headers.forEach(h => {
                    const hLower = h.toLowerCase();
                    if (studentKeywords.some(k => hLower.includes(k))) score += 2;
                });

                if (headers.length >= 5 && headers.length <= 30) score += 4;
                if (rows.length > 2) score += rows.length;

                if (score > bestScore) {
                    bestScore = score;
                    bestTable = {
                        table: tbl,
                        tblIdx: tblIdx,
                        headers: headers,
                        rows: rows
                    };
                }
            });

            if (!bestTable || bestScore < 10 || bestTable.headers.length < 4) {
                const lblMsg = document.querySelector('[id*="lblMsg"], [id*="lblMessage"], .alert, .text-danger');
                const msgText = lblMsg ? lblMsg.innerText.trim() : "";
                return {
                    found: false,
                    tableCount: tables.length,
                    portalMessage: msgText,
                    reason: msgText ? ("Portal notice: " + msgText) : "No student GridView loaded yet. Please select Session & Class and click 'Fetch Students'."
                };
            }

            const rawHeaders = bestTable.headers;
            const rows = bestTable.rows;
            const parsedRows = [];
            const rowActions = [];

            let dataStartIdx = 1;
            const hasThInFirst = rows[0].querySelectorAll('th').length > 0;
            if (!hasThInFirst && rows.length > 2) {
                const thInSecond = rows[1].querySelectorAll('th').length > 0;
                if (thInSecond) dataStartIdx = 2;
            }

            for (let rIdx = dataStartIdx; rIdx < rows.length; rIdx++) {
                const tr = rows[rIdx];
                const cells = Array.from(tr.querySelectorAll('td'));
                if (cells.length === 0) continue;

                const trText = tr.innerText.trim();
                if (/page \\d+ of|total record|first|previous|next|last/i.test(trText) && cells.length <= 2) {
                    continue;
                }

                const rowVals = cells.map(c => c.innerText.trim().replace(/\\s+/g, ' '));

                let actionInfo = null;
                cells.forEach((cell, colIdx) => {
                    const actionElem = cell.querySelector('a, input[type="submit"], input[type="button"], button');
                    if (actionElem) {
                        actionInfo = {
                            colIndex: colIdx,
                            tag: actionElem.tagName.toLowerCase(),
                            text: (actionElem.innerText || actionElem.value || '').trim()
                        };
                    }
                });

                parsedRows.push(rowVals);
                rowActions.push(actionInfo);
            }

            return {
                found: parsedRows.length > 0,
                headers: rawHeaders,
                rows: parsedRows,
                rowActions: rowActions,
                totalRows: parsedRows.length,
                score: bestScore
            };
        }
        """)

        if data.get("found"):
            headers = data.get("headers", [])
            rows = data.get("rows", [])
            self.cached_headers = headers
            self.cached_rows = rows
            self.cached_row_actions = data.get("rowActions", [])

            self.log(
                "SUCCESS",
                f"Extracted real student table! Found {len(rows)} real student entries.",
                f"Scraped {len(headers)} columns directly from live portal GridView."
            )

            if not self.school_name:
                self._extract_school_name_internal()

            return {
                "success": True,
                "found": True,
                "headers": headers,
                "rows": rows,
                "row_actions": self.cached_row_actions,
                "total_rows": len(rows),
                "school_name": self.school_name or self.school_user,
                "message": f"Successfully extracted {len(rows)} real student records.",
                "reason": f"Scraped {len(headers)} columns from portal GridView."
            }
        else:
            reason = data.get("reason", "No student rows found on page.")
            self.log("WARNING", "No student data rows currently loaded.", f"Reason: {reason}")
            return {
                "success": True,
                "found": False,
                "headers": [],
                "rows": [],
                "total_rows": 0,
                "message": "No student records found on the portal page.",
                "reason": reason
            }

    def deep_scrape_profiles(self, selected_indices: List[int]) -> Dict[str, Any]:
        """Deep scrapes full student profile forms on the live portal."""
        def _task():
            self._ensure_browser()
            if not selected_indices:
                return {"success": False, "message": "No rows selected."}

            total_to_process = len(selected_indices)
            self.log("ACTION", f"Deep scraping profiles for {total_to_process} student(s) on portal...", "Sequential form scraping.")

            processed = 0
            new_keys = set()

            for step_idx, row_idx in enumerate(selected_indices, start=1):
                if row_idx < 0 or row_idx >= len(self.cached_rows):
                    continue

                student_name = self.cached_rows[row_idx][2] if len(self.cached_rows[row_idx]) > 2 else f"Row {row_idx + 1}"
                self.log("ACTION", f"[{step_idx}/{total_to_process}] Scraping profile for {student_name}...", f"Row {row_idx}.")

                click_res = self.page.evaluate("""
                (targetRowIdx) => {
                    const tables = Array.from(document.querySelectorAll('table'));
                    for (const tbl of tables) {
                        const rows = Array.from(tbl.querySelectorAll('tr'));
                        if (rows.length < 2) continue;
                        let dataRows = [];
                        for (let i = 1; i < rows.length; i++) {
                            if (rows[i].querySelectorAll('td').length > 3) dataRows.push(rows[i]);
                        }
                        if (dataRows.length > targetRowIdx) {
                            const targetTr = dataRows[targetRowIdx];
                            const actionElem = targetTr.querySelector('a, input[type="submit"], input[type="button"], button');
                            if (actionElem) {
                                actionElem.click();
                                return { clicked: true, text: actionElem.innerText || actionElem.value };
                            }
                        }
                    }
                    return { clicked: false, reason: "No clickable action button in this row." };
                }
                """, row_idx)

                if not click_res.get("clicked"):
                    continue

                time.sleep(2.0)

                fields = self.page.evaluate("""
                () => {
                    const data = {};
                    const inputs = Array.from(document.querySelectorAll('input:not([type="hidden"]):not([type="submit"]):not([type="button"]), select, textarea'));
                    inputs.forEach(inp => {
                        let lbl = '';
                        if (inp.id) {
                            const l = document.querySelector(`label[for="${inp.id}"]`);
                            if (l) lbl = l.innerText.trim();
                        }
                        if (!lbl && inp.parentElement) {
                            const p = inp.parentElement.innerText.replace(inp.value || '', '').trim();
                            if (p && p.length < 50) lbl = p;
                        }
                        if (!lbl) lbl = inp.placeholder || inp.name || inp.id;
                        lbl = lbl.replace(/[:*]/g, '').trim();

                        let v = '';
                        if (inp.tagName.toLowerCase() === 'select') {
                            v = inp.options[inp.selectedIndex] ? inp.options[inp.selectedIndex].text.trim() : '';
                        } else {
                            v = inp.value ? inp.value.trim() : '';
                        }
                        if (lbl && v) data[lbl] = v;
                    });
                    return data;
                }
                """)

                if fields:
                    new_keys.update(fields.keys())
                    self.log("SUCCESS", f"Extracted {len(fields)} fields for {student_name}.", f"Fields: {', '.join(list(fields.keys())[:3])}...")
                    processed += 1

                self.page.evaluate("""
                () => {
                    const btn = document.querySelector('.close, [data-dismiss="modal"], [data-bs-dismiss="modal"], input[value*="वापस"], input[value*="Cancel"]');
                    if (btn) btn.click();
                }
                """)
                time.sleep(1.0)

            return {"success": True, "processed_count": processed, "fields": list(new_keys)}

        return self._execute(_task, timeout=120.0)

    def close(self):
        def _task():
            self._cleanup_resources()
            self.log("INFO", "Browser session closed.", "Playwright resources released.")
            return {"success": True}

        return self._execute(_task, timeout=10.0)

    def get_status(self) -> Dict[str, Any]:
        if self.school_name:
            self.school_name = self._clean_school_name_text(self.school_name)
        return {
            "browser_running": self.is_running,
            "current_url": self.current_url,
            "login_detected": self.login_detected,
            "school_user": self.school_user,
            "school_name": self.school_name,
            "has_table": len(self.cached_rows) > 0,
            "total_rows": len(self.cached_rows)
        }
