/**
 * RajPSP Student Profile Scraper Frontend Engine
 * 
 * - Seamless in-dashboard background authentication against Rajasthan PSP portal
 * - Automated live form injection, SHA512 hashing, postback handling
 * - Single-click live extraction of student records (PSP_UpdateStudentProfileDataEntry.aspx)
 * - Individual & Multiple Row/Column Copy to Clipboard (TSV / One-per-line)
 * - Individual & Multiple Row Deletion + Individual Column Deletion
 * - Instant Customized Excel (.xlsx) Download reflecting deleted rows and columns
 * - Restore Original Data capability
 * - Signal Blue (#0057FF) and Porcelain (#F8F7F4) design system
 * - STRICTLY ZERO MOCK DATA AT ANY COST.
 */

const state = {
  isLoggedIn: false,
  schoolUser: "",
  schoolName: "",
  headers: [],
  rows: [],
  originalHeaders: [],
  originalRows: [],
  selectedIndices: new Set(),
  lastClickedRowIndex: null,
  isMouseDown: false,
  dragStartIndex: null,
  dragInitialSelection: new Set(),
  selectedColumnIndices: new Set(),
  lastClickedColIndex: null,
  isColMouseDown: false,
  colDragStartIndex: null,
  colDragInitialSelection: new Set(),
  logEntries: [],
  currentLogFilter: "ALL",
  isDrawerOpen: false,
  isLoginCardOpen: true,
  pollTimer: null,
  lastLogIndex: 0
};

// Initialize Dashboard
document.addEventListener("DOMContentLoaded", () => {
  addLog(
    "INFO",
    "RVS SAH Dashboard initialized.",
    "Engine active with Signal Blue (#0057FF) & Porcelain (#F8F7F4) styling. Strictly zero mock data."
  );

  clearDropdowns();
  updateSelectionUI();

  // Provoke portal login page in background and fetch live Captcha
  initLoginCaptcha();

  // Pre-resolve School PSP Code on blur for rapid validation
  const unameInput = document.getElementById("loginUsername");
  if (unameInput) {
    unameInput.addEventListener("blur", async () => {
      const code = unameInput.value.trim();
      if (!code || state.isLoggedIn) return;
      
      addLog("ACTION", `Verifying School Code "${code}" on Rajasthan portal...`, "Validating school identity in background.");
      updateFloatingStatus(`Verifying School Code ${code}...`);

      try {
        const res = await callBackend("check-school-code", "POST", { username: code });
        if (res && res.valid) {
          addLog("SUCCESS", `School Code "${code}" verified! Internal School ID: ${res.school_id}.`, "Authentication ready.");
          showToast(`School code verified (Internal ID: ${res.school_id})`, "info");
          updateFloatingStatus(`School ${code} verified & ready for sign-in`);
        } else if (res && res.error) {
          addLog("WARNING", `School Code feedback: ${res.error}`, "Website returned validation warning.");
        }
      } catch (e) {
        // Ignore background network error
      }
    });

    // Allow Enter key in inputs to trigger submit
    unameInput.addEventListener("keydown", (e) => { if (e.key === "Enter") document.getElementById("loginPassword").focus(); });
  }

  const pwdInput = document.getElementById("loginPassword");
  if (pwdInput) {
    pwdInput.addEventListener("keydown", (e) => { if (e.key === "Enter") document.getElementById("loginCaptcha").focus(); });
  }

  const capInput = document.getElementById("loginCaptcha");
  if (capInput) {
    capInput.addEventListener("keydown", (e) => { if (e.key === "Enter") submitPortalLogin(); });
  }

  // Start continuous status and background log synchronization
  startStatusPolling();
});

// UI Toggles: Drawer and Login Card
function toggleActivityDrawer() {
  state.isDrawerOpen = !state.isDrawerOpen;
  const drawer = document.getElementById("activityDrawer");
  const overlay = document.getElementById("drawerOverlay");

  if (state.isDrawerOpen) {
    drawer.classList.add("open");
    overlay.classList.add("open");
  } else {
    drawer.classList.remove("open");
    overlay.classList.remove("open");
  }
}

function toggleLoginCard() {
  const section = document.getElementById("loginSection");
  const btnLabel = document.getElementById("loginBtnLabel");
  state.isLoginCardOpen = !state.isLoginCardOpen;

  if (state.isLoginCardOpen) {
    section.classList.remove("collapsed");
    if (btnLabel) btnLabel.textContent = "Hide Login";
  } else {
    section.classList.add("collapsed");
    if (btnLabel) btnLabel.textContent = "School Login";
  }
}

function updateFloatingStatus(text) {
  const el = document.getElementById("floatingStatusText");
  if (el) el.textContent = text;
}

function cleanSchoolName(name) {
  if (!name || typeof name !== "string") return "";
  let clean = name.trim();
  clean = clean.replace(/^Welcome\s*[-–—:]\s*/i, "");
  clean = clean.split(/[\r\n]+/)[0].trim();
  const junkPatterns = [
    /मुख्य\s*पृष्ठ/g,
    /स्कूल\s*सम्पर्क\s*विवरण/g,
    /पासवर्ड\s*बदलें/g,
    /लॉगआउट/g,
    /logout/gi,
    /help/gi,
    /home/gi
  ];
  for (const p of junkPatterns) {
    clean = clean.replace(p, " ");
  }
  clean = clean.replace(/^[|\s\-–—:]+|[|\s\-–—:]+$/g, "").replace(/\s{2,}/g, " ").trim();
  return clean;
}

// Display Authenticated School Name in Green under Title
function updateSchoolNameUI(schoolName) {
  const subtitleEl = document.getElementById("brandSubtitle");
  if (!subtitleEl) return;

  if (state.isLoggedIn && (schoolName || state.schoolName || state.schoolUser)) {
    let dispName = schoolName || state.schoolName || `School (${state.schoolUser})`;
    dispName = cleanSchoolName(dispName) || `School (${state.schoolUser})`;
    state.schoolName = dispName;
    subtitleEl.innerHTML = `<span class="school-name-green" title="${escapeHtml(dispName)}"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: -2px; margin-right: 4px; flex-shrink: 0;"><path d="M3 21h18"></path><path d="M5 21V7l7-4 7 4v14"></path><path d="M9 10a2 2 0 1 1 0-4 2 2 0 0 1 0 4z"></path></svg>${escapeHtml(dispName)}</span>`;
  } else {
    subtitleEl.innerHTML = `Rajasthan School Profile Data Extraction &bull; PSP_UpdateStudentProfileDataEntry.aspx`;
  }
}

// Live Portal Captcha Handling
async function initLoginCaptcha() {
  setCaptchaLoading(true);
  addLog("ACTION", "Connecting to live portal login page in background...", "Fetching fresh Captcha challenge from rajpsp.rajasthan.gov.in.");
  updateFloatingStatus("Fetching live Rajasthan portal Captcha...");

  try {
    const res = await callBackend("init-login", "POST");
    if (res && res.captcha_b64) {
      setCaptchaImage(res.captcha_b64);
      addLog("SUCCESS", "Captured live CAPTCHA from Rajasthan PSP server.", "Ready for user credentials.");
      updateFloatingStatus("Live Captcha ready &bull; Awaiting school credentials");
    } else {
      setCaptchaLoading(false, "Failed. Click ↻ to retry.");
      addLog("WARNING", "Could not fetch Captcha image from portal.", res ? res.message : "Network error.");
      updateFloatingStatus("Captcha challenge failed &bull; Click refresh");
    }
  } catch (e) {
    setCaptchaLoading(false, "Connection error.");
    addLog("ERROR", `Failed to load portal Captcha: ${e}`, "Backend API error.");
    updateFloatingStatus("Connection error with backend server");
  }
}

async function refreshCaptcha() {
  setCaptchaLoading(true);
  addLog("ACTION", "Requesting fresh Captcha image from portal...", "User triggered Captcha refresh.");
  updateFloatingStatus("Refreshing live Captcha from portal...");

  try {
    const res = await callBackend("refresh-captcha", "POST");
    if (res && res.captcha_b64) {
      setCaptchaImage(res.captcha_b64);
      addLog("SUCCESS", "Fetched fresh live CAPTCHA image.", "Updated image display.");
      updateFloatingStatus("Fresh Captcha loaded");
    } else {
      setCaptchaLoading(false, "Retry");
    }
  } catch (e) {
    setCaptchaLoading(false, "Error");
    addLog("ERROR", `Captcha refresh failed: ${e}`, "API error.");
  }
}

function setCaptchaLoading(isLoading, errText = "") {
  const loadingText = document.getElementById("captchaLoadingText");
  const img = document.getElementById("captchaImg");
  if (isLoading) {
    if (loadingText) {
      loadingText.textContent = "Loading...";
      loadingText.style.display = "inline";
    }
    if (img) img.style.display = "none";
  } else if (errText) {
    if (loadingText) {
      loadingText.textContent = errText;
      loadingText.style.display = "inline";
    }
    if (img) img.style.display = "none";
  }
}

function setCaptchaImage(b64Src) {
  const loadingText = document.getElementById("captchaLoadingText");
  const img = document.getElementById("captchaImg");
  if (loadingText) loadingText.style.display = "none";
  if (img) {
    img.src = b64Src;
    img.style.display = "inline";
  }
}

// In-Dashboard Portal Login Submission
async function submitPortalLogin() {
  const username = (document.getElementById("loginUsername").value || "").trim();
  const password = (document.getElementById("loginPassword").value || "").trim();
  const captcha = (document.getElementById("loginCaptcha").value || "").trim();

  const feedbackBox = document.getElementById("loginFeedbackBox");
  const feedbackIcon = document.getElementById("feedbackIcon");
  const feedbackText = document.getElementById("loginFeedbackText");
  const btn = document.getElementById("btnSubmitLogin");

  if (!username) {
    showToast("Please enter your School PSP Code.", "error");
    document.getElementById("loginUsername").focus();
    return;
  }
  if (!password) {
    showToast("Please enter your Password.", "error");
    document.getElementById("loginPassword").focus();
    return;
  }
  if (!captcha) {
    showToast("Please enter the Captcha characters.", "error");
    document.getElementById("loginCaptcha").focus();
    return;
  }

  const origBtnContent = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = `<span>Signing In...</span>`;
  feedbackBox.style.display = "none";

  addLog(
    "ACTION",
    `Submitting credentials for School Code "${username}"...`,
    "Injecting username, generating SHA512 portal hash with server salt, and posting live form."
  );
  updateFloatingStatus(`Authenticating School ${username} on Rajasthan portal...`);
  showToast("Authenticating on Rajasthan portal...", "info");

  try {
    const res = await callBackend("submit-login", "POST", { username, password, captcha });

    if (res && res.success) {
      // SUCCESSFUL LOGIN
      state.isLoggedIn = true;
      state.schoolUser = username;

      // Update Feedback Box
      feedbackBox.className = "feedback-banner success";
      feedbackIcon.innerHTML = "&#10003;";
      feedbackText.innerHTML = `<strong>Authentication Successful!</strong> ${escapeHtml(res.message || "Session active.")} Navigated to PSP_UpdateStudentProfileDataEntry.aspx.`;
      feedbackBox.style.display = "flex";

      // Update Form Grid to Authenticated Banner
      document.getElementById("loginInputsRow").style.display = "none";
      const authStrip = document.getElementById("authenticatedStrip");
      authStrip.style.display = "flex";
      document.getElementById("authSchoolUser").textContent = username;

      // Update Header Status Pill
      const pill = document.getElementById("headerAuthPill");
      pill.className = "auth-status-pill authenticated";
      document.getElementById("headerStatusText").textContent = `School: ${username}`;

      // Update Subtitle with School Name in green
      if (res.school_name) {
        state.schoolName = res.school_name;
        updateSchoolNameUI(res.school_name);
      } else {
        updateSchoolNameUI(username);
      }

      // Show Switch School Button in Header, Hide School Login Button
      document.getElementById("btnSwitchSchool").style.display = "inline-flex";
      document.getElementById("btnToggleLogin").style.display = "none";

      // Collapse Login Card automatically after 1.5s to give full viewport to the student workspace
      setTimeout(() => {
        if (state.isLoggedIn) {
          const section = document.getElementById("loginSection");
          section.classList.add("collapsed");
          state.isLoginCardOpen = false;
        }
      }, 1600);

      // Populate Live Dropdowns
      if (res.sessions && res.sessions.length > 0) {
        populateSelect("sessionSelect", res.sessions, "-- Select Session --");
      }
      if (res.classes && res.classes.length > 0) {
        populateSelect("classSelect", res.classes, "-- Select Class --");
      }

      // Update Empty State Callout
      const emptyReason = document.getElementById("emptyStateReason");
      if (emptyReason) {
        emptyReason.innerHTML = `<b>Authenticated as School ${username}.</b> Please select an Academic Session and Class in the top ribbon, then click <b>"Fetch Students"</b>.`;
      }

      addLog("SUCCESS", `Authentication confirmed for School "${username}"!`, res.reason || "Portal session established.");
      updateFloatingStatus(`School ${username} authenticated &bull; Ready to select Class`);
      showToast("Signed in! Session and Class dropdowns loaded.", "success");

    } else {
      // LOGIN FAILED: Show EXACT technical feedback from actual Rajasthan portal
      const errorMsg = res && res.error ? res.error : "Login Failed. Please check your credentials.";

      feedbackBox.className = "feedback-banner error";
      feedbackIcon.innerHTML = "&#9888;";
      feedbackText.innerHTML = `<strong>Website Feedback:</strong> ${escapeHtml(errorMsg)}`;
      feedbackBox.style.display = "flex";

      // Update Captcha Image if new challenge returned
      if (res && res.captcha_b64) {
        setCaptchaImage(res.captcha_b64);
      } else {
        refreshCaptcha();
      }

      // Clear password & captcha
      document.getElementById("loginPassword").value = "";
      document.getElementById("loginCaptcha").value = "";
      document.getElementById("loginCaptcha").focus();

      addLog("ERROR", `Portal login rejected: ${errorMsg}`, res && res.reason ? res.reason : "Website rejected authentication attempt.");
      updateFloatingStatus(`Login failed: ${errorMsg}`);
      showToast(`Login failed: ${errorMsg}`, "error");
    }
  } catch (e) {
    feedbackBox.className = "feedback-banner error";
    feedbackIcon.innerHTML = "&#9888;";
    feedbackText.innerHTML = `<strong>Execution Error:</strong> ${escapeHtml(String(e))}`;
    feedbackBox.style.display = "flex";
    addLog("ERROR", `Login execution failure: ${e}`, "Backend communication error.");
    showToast("Server connection error.", "error");
  } finally {
    btn.innerHTML = origBtnContent;
    btn.disabled = false;
  }
}

// Logout & Reset Session
async function logoutSession() {
  addLog("ACTION", "Logging out of school session...", "Closing Playwright context.");
  updateFloatingStatus("Closing session & logging out...");

  try {
    await callBackend("close-browser", "POST");
  } catch (e) {}

  state.isLoggedIn = false;
  state.schoolUser = "";
  state.schoolName = "";
  updateSchoolNameUI("");

  // Reset Login UI
  document.getElementById("loginInputsRow").style.display = "grid";
  document.getElementById("authenticatedStrip").style.display = "none";
  document.getElementById("loginFeedbackBox").style.display = "none";

  document.getElementById("loginUsername").value = "";
  document.getElementById("loginPassword").value = "";
  document.getElementById("loginCaptcha").value = "";

  // Reset Header Status
  const pill = document.getElementById("headerAuthPill");
  pill.className = "auth-status-pill";
  document.getElementById("headerStatusText").textContent = "Disconnected";

  document.getElementById("btnSwitchSchool").style.display = "none";
  const btnToggle = document.getElementById("btnToggleLogin");
  btnToggle.style.display = "inline-flex";
  document.getElementById("loginBtnLabel").textContent = "School Login";

  // Open Login Section
  const section = document.getElementById("loginSection");
  section.classList.remove("collapsed");
  state.isLoginCardOpen = true;

  clearDropdowns();
  clearTable("Logged out. Please log in above to access student records.");

  // Fetch fresh captcha
  initLoginCaptcha();
  showToast("Logged out successfully.", "info");
}

function clearDropdowns() {
  const sess = document.getElementById("sessionSelect");
  const cls = document.getElementById("classSelect");
  if (sess) sess.innerHTML = '<option value="">-- Waiting for Login --</option>';
  if (cls) cls.innerHTML = '<option value="">-- Waiting for Login --</option>';
}

// Scrape Session and Class Dropdowns from Live Portal DOM
async function fetchDropdownOptions() {
  if (!state.isLoggedIn) {
    showToast("Please log in with your school credentials first.", "error");
    toggleLoginCard();
    return;
  }

  addLog("ACTION", "Scraping Session & Class options from portal...", "Querying <select> dropdowns in live page DOM.");
  updateFloatingStatus("Syncing dropdown options from portal...");

  try {
    const res = await callBackend("get-dropdowns", "GET");
    if (res && res.success && (res.sessions.length > 0 || res.classes.length > 0)) {
      populateSelect("sessionSelect", res.sessions, "-- Select Session --");
      populateSelect("classSelect", res.classes, "-- Select Class --");
      showToast(`Synced ${res.sessions.length} sessions, ${res.classes.length} classes from portal.`, "success");
      updateFloatingStatus(`Synced ${res.sessions.length} sessions & ${res.classes.length} classes`);
    } else {
      clearDropdowns();
      const reason = res.reason || "Not on Profile Entry page. Ensure login is active.";
      addLog("WARNING", "Could not fetch dropdowns from portal.", reason);
      showToast(res.message || "Dropdowns not found on portal.", "error");
    }
  } catch (e) {
    addLog("ERROR", `Failed to scrape dropdowns: ${e}`, "API error.");
  }
}

function populateSelect(elementId, options, placeholder) {
  const select = document.getElementById(elementId);
  if (!select) return;
  select.innerHTML = "";

  const defaultOpt = document.createElement("option");
  defaultOpt.value = "";
  defaultOpt.textContent = placeholder;
  select.appendChild(defaultOpt);

  if (Array.isArray(options)) {
    options.forEach(opt => {
      if (!opt.text) return;
      const o = document.createElement("option");
      o.value = opt.value || opt.text;
      o.textContent = opt.text;
      select.appendChild(o);
    });
  }
}

// Submit Session/Class on Live Portal & Extract Real GridView Table
async function submitViewStudents() {
  const sessionVal = document.getElementById("sessionSelect").value;
  const classVal = document.getElementById("classSelect").value;
  const btn = document.getElementById("btnLoadStudents");

  if (!state.isLoggedIn) {
    showToast("Please sign in first.", "error");
    toggleLoginCard();
    return;
  }

  if (!classVal) {
    showToast("Please select a Class from the dropdown.", "error");
    document.getElementById("classSelect").focus();
    return;
  }

  const origBtn = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = `<span>Fetching...</span>`;

  addLog("ACTION", `Requesting records for Class "${classVal}" (Session: "${sessionVal}")...`, "Staging selection on portal and waiting for response.");
  updateFloatingStatus(`Fetching records for Class ${classVal}...`);
  showToast("Requesting student list from Rajasthan portal...", "info");

  try {
    const res = await callBackend("submit-view", "POST", { sessionVal, classVal });
    if (res && res.found) {
      if (res.school_name && res.school_name !== state.schoolName) {
        state.schoolName = res.school_name;
        updateSchoolNameUI(res.school_name);
      }

      state.originalHeaders = JSON.parse(JSON.stringify(res.headers));
      state.originalRows = JSON.parse(JSON.stringify(res.rows));

      renderRealTable(res.headers, res.rows, true);
      addLog("SUCCESS", `Extracted ${res.total_rows} real student records on single click!`, `Headers: [${res.headers.join(", ")}]`);
      updateFloatingStatus(`Loaded ${res.total_rows} student records for Class ${classVal}`);
      showToast(`Extracted ${res.total_rows} real student records!`, "success");
    } else {
      clearTable(res ? res.reason : "No student table currently returned by portal for selected criteria.");
      addLog("WARNING", "Portal returned no student table.", res ? res.reason : "Empty result.");
      updateFloatingStatus("No student records found on portal");
      showToast(res && res.message ? res.message : "No student records found.", "info");
    }
  } catch (e) {
    addLog("ERROR", `Submission error: ${e}`, "Exception during portal view execution.");
    showToast("Failed to fetch students from portal.", "error");
  } finally {
    btn.innerHTML = origBtn;
    btn.disabled = false;
  }
}

// Detect Student Table from Current Page DOM
async function detectStudentTable() {
  if (!state.isLoggedIn) {
    showToast("Please sign in first.", "error");
    toggleLoginCard();
    return;
  }

  addLog("ACTION", "Scanning current page DOM for student GridView table...", "User clicked Detect Table.");
  updateFloatingStatus("Scanning DOM for student table...");

  try {
    const res = await callBackend("detect-table", "GET");
    if (res && res.found) {
      if (res.school_name && res.school_name !== state.schoolName) {
        state.schoolName = res.school_name;
        updateSchoolNameUI(res.school_name);
      }

      state.originalHeaders = JSON.parse(JSON.stringify(res.headers));
      state.originalRows = JSON.parse(JSON.stringify(res.rows));

      renderRealTable(res.headers, res.rows, true);
      addLog("SUCCESS", `Detected ${res.total_rows} real student rows in DOM!`, "DOM scan successful.");
      updateFloatingStatus(`Detected ${res.total_rows} student rows`);
      showToast(`Detected ${res.total_rows} real student rows!`, "success");
    } else {
      clearTable(res ? res.reason : "No student table found on current page.");
      showToast(res ? res.reason : "No student table found on page.", "info");
    }
  } catch (e) {
    addLog("ERROR", `Table detection error: ${e}`, "Exception in detect_student_table.");
  }
}

// Render REAL Data Table with Actions & Customization
function renderRealTable(headers, rows, isFreshFetch = false) {
  state.headers = headers || [];
  state.rows = rows || [];

  const emptyState = document.getElementById("emptyState");
  const scrollWrapper = document.getElementById("tableScrollWrapper");
  const thead = document.getElementById("tableHead");
  const tbody = document.getElementById("tableBody");

  if (!state.rows || state.rows.length === 0) {
    clearTable("Zero student rows found in extracted table.");
    return;
  }

  if (isFreshFetch) {
    state.selectedIndices = new Set();
    state.rows.forEach((_, idx) => state.selectedIndices.add(idx));
    state.selectedColumnIndices = new Set();
    state.lastClickedColIndex = null;
  } else {
    // Prune invalid selected indices
    const pruned = new Set();
    state.selectedIndices.forEach(idx => {
      if (idx < state.rows.length) pruned.add(idx);
    });
    state.selectedIndices = pruned;

    const prunedCols = new Set();
    state.selectedColumnIndices.forEach(idx => {
      if (idx < state.headers.length) prunedCols.add(idx);
    });
    state.selectedColumnIndices = prunedCols;
  }

  emptyState.style.display = "none";
  scrollWrapper.style.display = "block";

  // Build Table Header
  thead.innerHTML = "";
  const headerTr = document.createElement("tr");

  // 1. Master Checkbox Column
  const masterTh = document.createElement("th");
  masterTh.className = "cell-checkbox";
  masterTh.innerHTML = `<input type="checkbox" class="checkbox-custom" id="masterCheckbox" checked onchange="toggleMasterCheckbox(this.checked)" title="Select/Deselect All">`;
  headerTr.appendChild(masterTh);

  // 2. Row Actions Column Header
  const actionTh = document.createElement("th");
  actionTh.style.width = "62px";
  actionTh.style.textAlign = "center";
  actionTh.textContent = "Actions";
  headerTr.appendChild(actionTh);

  // 3. Data Column Headers with Selection, Copy & Delete Tools
  state.headers.forEach((h, colIdx) => {
    const th = document.createElement("th");
    th.className = "col-selectable" + (state.selectedColumnIndices.has(colIdx) ? " col-selected" : "");
    th.dataset.colIdx = colIdx;
    th.title = `Click to select column (${h}). Shift+Click for range.`;
    th.innerHTML = `
      <div class="th-content">
        <span class="th-title" title="${escapeHtml(h)}">${escapeHtml(h)}</span>
        <div class="th-actions">
          <button class="th-btn" onclick="event.stopPropagation(); copyColumn(${colIdx})" title="Copy all values in this column (${escapeHtml(h)})">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
              <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
            </svg>
          </button>
          <button class="th-btn th-delete-btn" onclick="event.stopPropagation(); deleteColumn(${colIdx})" title="Delete this column from table & Excel download">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        </div>
      </div>
    `;
    th.addEventListener("mousedown", (e) => handleColHeaderMouseDown(colIdx, e));
    th.addEventListener("mouseenter", () => handleColHeaderMouseEnter(colIdx));
    th.addEventListener("click", (e) => handleColHeaderClick(colIdx, e));
    headerTr.appendChild(th);
  });
  thead.appendChild(headerTr);

  // Build Table Rows
  tbody.innerHTML = "";
  state.rows.forEach((row, rowIdx) => {
    const tr = document.createElement("tr");
    tr.id = `row-${rowIdx}`;
    tr.dataset.rowIdx = rowIdx;
    const isSelected = state.selectedIndices.has(rowIdx);
    if (isSelected) tr.classList.add("selected");

    // Checkbox Cell
    const checkTd = document.createElement("td");
    checkTd.className = "cell-checkbox";
    checkTd.innerHTML = `<input type="checkbox" class="checkbox-custom" id="chk-${rowIdx}" ${isSelected ? "checked" : ""}>`;
    tr.appendChild(checkTd);

    // Row Action Cell (Copy Row & Delete Row)
    const actionTd = document.createElement("td");
    actionTd.className = "cell-row-actions";
    actionTd.innerHTML = `
      <button class="row-action-btn" onclick="event.stopPropagation(); copyRow(${rowIdx})" title="Copy this student row to clipboard (Excel formatted)">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
          <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
        </svg>
      </button>
      <button class="row-action-btn row-delete-btn" onclick="event.stopPropagation(); deleteRow(${rowIdx})" title="Delete this student row from table & Excel download">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="3 6 5 6 21 6"></polyline>
          <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
        </svg>
      </button>
    `;
    tr.appendChild(actionTd);

    // Data Cells with Column Index Tracking & Column Highlight
    row.forEach((cellVal, colIdx) => {
      const td = document.createElement("td");
      td.dataset.colIdx = colIdx;
      if (state.selectedColumnIndices.has(colIdx)) {
        td.classList.add("col-selected");
      }
      td.textContent = cellVal;
      tr.appendChild(td);
    });

    // Excel Selection Event Handlers
    tr.addEventListener("mousedown", (e) => handleRowMouseDown(rowIdx, e));
    tr.addEventListener("mouseenter", () => handleRowMouseEnter(rowIdx));
    tr.addEventListener("click", (e) => handleRowClick(rowIdx, e));

    const chk = checkTd.querySelector("input");
    if (chk) {
      chk.addEventListener("click", (e) => {
        e.stopPropagation();
        handleCheckboxClick(rowIdx, chk.checked, e);
      });
    }

    tbody.appendChild(tr);
  });

  updateSelectionUI();
  updateColumnSelectionUI();
}

function clearTable(reason) {
  state.headers = [];
  state.rows = [];
  state.selectedIndices.clear();
  state.lastClickedRowIndex = null;
  state.selectedColumnIndices.clear();
  state.lastClickedColIndex = null;

  const emptyState = document.getElementById("emptyState");
  const scrollWrapper = document.getElementById("tableScrollWrapper");
  const emptyReason = document.getElementById("emptyStateReason");

  if (emptyState) emptyState.style.display = "flex";
  if (scrollWrapper) scrollWrapper.style.display = "none";
  if (emptyReason) {
    emptyReason.innerHTML = `No student data currently loaded.<br><b>Exact Reason:</b> ${reason || "Student table has not been loaded from the live portal."}`;
  }

  updateSelectionUI();
  updateColumnSelectionUI();
}

// ============================================================================
// EXCEL-LIKE MULTI-ROW SELECTION HANDLERS
// ============================================================================

// 1. Row Click: Shift+Click range, Ctrl+Click multi-select, Click single-row
function handleRowClick(rowIdx, event) {
  if (event.target.closest("button") || event.target.closest("input")) return;

  if (event.shiftKey && state.lastClickedRowIndex !== null) {
    // Shift + Click: Continuous Range Selection (Excel behavior)
    const start = Math.min(state.lastClickedRowIndex, rowIdx);
    const end = Math.max(state.lastClickedRowIndex, rowIdx);
    for (let i = start; i <= end; i++) {
      state.selectedIndices.add(i);
    }
  } else if (event.ctrlKey || event.metaKey) {
    // Ctrl / Cmd + Click: Toggle individual row (Excel behavior)
    if (state.selectedIndices.has(rowIdx)) {
      state.selectedIndices.delete(rowIdx);
    } else {
      state.selectedIndices.add(rowIdx);
    }
    state.lastClickedRowIndex = rowIdx;
  } else {
    // Regular Click: Select this row exclusively (Excel behavior)
    state.selectedIndices.clear();
    state.selectedIndices.add(rowIdx);
    state.lastClickedRowIndex = rowIdx;
  }

  syncAllRowSelectionClasses();
  updateSelectionUI();
}

// 2. Checkbox Click: Toggle or Shift+Click range toggle
function handleCheckboxClick(rowIdx, isChecked, event) {
  if (event && event.shiftKey && state.lastClickedRowIndex !== null) {
    const start = Math.min(state.lastClickedRowIndex, rowIdx);
    const end = Math.max(state.lastClickedRowIndex, rowIdx);
    for (let i = start; i <= end; i++) {
      if (isChecked) state.selectedIndices.add(i);
      else state.selectedIndices.delete(i);
    }
  } else {
    if (isChecked) state.selectedIndices.add(rowIdx);
    else state.selectedIndices.delete(rowIdx);
    state.lastClickedRowIndex = rowIdx;
  }
  syncAllRowSelectionClasses();
  updateSelectionUI();
}

// 3. Mouse Down: Initiate click & drag selection marquee
function handleRowMouseDown(rowIdx, event) {
  if (event.target.closest("button") || event.target.closest("input") || event.button !== 0) return;
  state.isMouseDown = true;
  state.dragStartIndex = rowIdx;
  document.body.classList.add("is-dragging-rows");

  if (!event.shiftKey && !event.ctrlKey && !event.metaKey) {
    state.dragInitialSelection = new Set();
    state.dragInitialSelection.add(rowIdx);
    state.selectedIndices = new Set(state.dragInitialSelection);
    state.lastClickedRowIndex = rowIdx;
    syncAllRowSelectionClasses();
    updateSelectionUI();
  } else {
    state.dragInitialSelection = new Set(state.selectedIndices);
  }
}

// 4. Mouse Enter: Dragging over rows to select multiple rows
function handleRowMouseEnter(rowIdx) {
  if (!state.isMouseDown || state.dragStartIndex === null) return;
  const start = Math.min(state.dragStartIndex, rowIdx);
  const end = Math.max(state.dragStartIndex, rowIdx);

  state.selectedIndices = new Set(state.dragInitialSelection);
  for (let i = start; i <= end; i++) {
    state.selectedIndices.add(i);
  }
  syncAllRowSelectionClasses();
  updateSelectionUI();
}

// Global mouse up to terminate drag
document.addEventListener("mouseup", () => {
  if (state.isMouseDown) {
    state.isMouseDown = false;
    document.body.classList.remove("is-dragging-rows");
    updateSelectionUI();
  }
  if (state.isColMouseDown) {
    state.isColMouseDown = false;
    document.body.classList.remove("is-dragging-cols");
    updateColumnSelectionUI();
  }
});

// ============================================================================
// EXCEL-LIKE MULTI-COLUMN SELECTION HANDLERS
// ============================================================================

function handleColHeaderClick(colIdx, event) {
  if (event.target.closest("button") || event.target.closest("input")) return;

  if (event.shiftKey && state.lastClickedColIndex !== null) {
    // Shift + Click: Continuous Range Selection of Columns (Excel behavior)
    const start = Math.min(state.lastClickedColIndex, colIdx);
    const end = Math.max(state.lastClickedColIndex, colIdx);
    for (let i = start; i <= end; i++) {
      state.selectedColumnIndices.add(i);
    }
  } else if (event.ctrlKey || event.metaKey) {
    // Ctrl / Cmd + Click: Toggle individual column (Excel behavior)
    if (state.selectedColumnIndices.has(colIdx)) {
      state.selectedColumnIndices.delete(colIdx);
    } else {
      state.selectedColumnIndices.add(colIdx);
    }
    state.lastClickedColIndex = colIdx;
  } else {
    // Regular Click: Select this column exclusively (Excel behavior)
    state.selectedColumnIndices.clear();
    state.selectedColumnIndices.add(colIdx);
    state.lastClickedColIndex = colIdx;
  }

  syncAllColumnSelectionClasses();
  updateColumnSelectionUI();
}

function handleColHeaderMouseDown(colIdx, event) {
  if (event.target.closest("button") || event.target.closest("input") || event.button !== 0) return;
  state.isColMouseDown = true;
  state.colDragStartIndex = colIdx;
  document.body.classList.add("is-dragging-cols");

  if (!event.shiftKey && !event.ctrlKey && !event.metaKey) {
    state.colDragInitialSelection = new Set();
    state.colDragInitialSelection.add(colIdx);
    state.selectedColumnIndices = new Set(state.colDragInitialSelection);
    state.lastClickedColIndex = colIdx;
    syncAllColumnSelectionClasses();
    updateColumnSelectionUI();
  } else {
    state.colDragInitialSelection = new Set(state.selectedColumnIndices);
  }
}

function handleColHeaderMouseEnter(colIdx) {
  if (!state.isColMouseDown || state.colDragStartIndex === null) return;
  const start = Math.min(state.colDragStartIndex, colIdx);
  const end = Math.max(state.colDragStartIndex, colIdx);

  state.selectedColumnIndices = new Set(state.colDragInitialSelection);
  for (let i = start; i <= end; i++) {
    state.selectedColumnIndices.add(i);
  }
  syncAllColumnSelectionClasses();
  updateColumnSelectionUI();
}

function syncAllColumnSelectionClasses() {
  const table = document.getElementById("studentDataTable") || document.querySelector("table.hero-table");
  if (!table) return;

  const ths = table.querySelectorAll("th[data-col-idx]");
  ths.forEach(th => {
    const idx = parseInt(th.dataset.colIdx, 10);
    if (state.selectedColumnIndices.has(idx)) {
      th.classList.add("col-selected");
    } else {
      th.classList.remove("col-selected");
    }
  });

  const tds = table.querySelectorAll("td[data-col-idx]");
  tds.forEach(td => {
    const idx = parseInt(td.dataset.colIdx, 10);
    if (state.selectedColumnIndices.has(idx)) {
      td.classList.add("col-selected");
    } else {
      td.classList.remove("col-selected");
    }
  });
}

function deselectAllColumns() {
  state.selectedColumnIndices.clear();
  state.lastClickedColIndex = null;
  syncAllColumnSelectionClasses();
  updateColumnSelectionUI();
}

function updateColumnSelectionUI() {
  const count = state.selectedColumnIndices.size;
  const pill = document.getElementById("colSelectionPill");
  const countEl = document.getElementById("selectedColCount");
  const btnDelete = document.getElementById("btnDeleteSelectedCols");
  const btnDeleteText = document.getElementById("deleteSelectedColsBtnText");
  const btnCopy = document.getElementById("btnCopySelectedCols");
  const btnDeselect = document.getElementById("btnDeselectCols");

  if (pill) pill.style.display = count > 0 ? "inline-flex" : "none";
  if (countEl) countEl.textContent = count;
  if (btnDelete) btnDelete.style.display = count > 0 ? "inline-flex" : "none";
  if (btnDeleteText) btnDeleteText.textContent = count > 1 ? `Delete (${count} Cols)` : `Delete Col`;
  if (btnCopy) btnCopy.style.display = count > 0 ? "inline-flex" : "none";
  if (btnDeselect) btnDeselect.style.display = count > 0 ? "inline-flex" : "none";

  const btnRestore = document.getElementById("btnRestoreTable");
  if (btnRestore) {
    const isCustomized = state.originalHeaders.length > 0 && (
      state.headers.length !== state.originalHeaders.length ||
      state.rows.length !== state.originalRows.length
    );
    btnRestore.style.display = isCustomized ? "inline-flex" : "none";
  }
}

// Delete Multiple Selected Columns
function deleteSelectedColumns() {
  const colIndices = Array.from(state.selectedColumnIndices).sort((a, b) => b - a); // descending order
  if (colIndices.length === 0) {
    showToast("No columns selected to delete.", "error");
    return;
  }

  const deletedNames = [];
  colIndices.forEach(idx => {
    if (idx >= 0 && idx < state.headers.length) {
      deletedNames.push(state.headers[idx]);
      state.headers.splice(idx, 1);
      state.rows.forEach(r => {
        r.splice(idx, 1);
      });
    }
  });

  state.selectedColumnIndices.clear();
  state.lastClickedColIndex = null;

  renderRealTable(state.headers, state.rows, false);
  showToast(`Deleted ${colIndices.length} column(s). Excel download will exclude them.`, "info");
  addLog("ACTION", `Deleted ${colIndices.length} column(s): [${deletedNames.reverse().join(", ")}] from working table.`, "Customized columns for Excel export.");
}

// Copy Multiple Selected Columns
async function copySelectedColumns() {
  const colIndices = Array.from(state.selectedColumnIndices).sort((a, b) => a - b);
  if (colIndices.length === 0) {
    showToast("No columns selected to copy.", "error");
    return;
  }

  const headerLine = colIndices.map(idx => state.headers[idx]).join("\t");
  const rowLines = state.rows.map(r => colIndices.map(idx => r[idx] || "").join("\t"));
  const tsv = [headerLine, ...rowLines].join("\n");

  if (navigator.clipboard) {
    await navigator.clipboard.writeText(tsv);
    showToast(`Copied ${colIndices.length} column(s) across ${state.rows.length} rows! Paste into Excel.`, "success");
    addLog("SUCCESS", `Copied ${colIndices.length} selected column(s) to clipboard.`, "TSV formatted with headers.");
  } else {
    showToast("Clipboard write permission unavailable.", "error");
  }
}

// Fast DOM synchronization
function syncAllRowSelectionClasses() {
  state.rows.forEach((_, idx) => {
    const isSel = state.selectedIndices.has(idx);
    const rowEl = document.getElementById(`row-${idx}`);
    const chk = document.getElementById(`chk-${idx}`);
    if (rowEl) {
      if (isSel) rowEl.classList.add("selected");
      else rowEl.classList.remove("selected");
    }
    if (chk) chk.checked = isSel;
  });
}

function toggleMasterCheckbox(isChecked) {
  state.selectedIndices.clear();
  state.rows.forEach((_, idx) => {
    const chk = document.getElementById(`chk-${idx}`);
    const rowEl = document.getElementById(`row-${idx}`);
    if (chk) chk.checked = isChecked;
    if (isChecked) {
      state.selectedIndices.add(idx);
      if (rowEl) rowEl.classList.add("selected");
    } else {
      if (rowEl) rowEl.classList.remove("selected");
    }
  });
  state.lastClickedRowIndex = null;
  updateSelectionUI();
}

function toggleSelectAll() {
  const isAll = state.selectedIndices.size === state.rows.length;
  toggleMasterCheckbox(!isAll);
}

function updateSelectionUI() {
  const selectedCount = state.selectedIndices.size;
  const totalCount = state.rows.length;

  const selCountEl = document.getElementById("selectedCount");
  const totCountEl = document.getElementById("totalRowCount");
  if (selCountEl) selCountEl.textContent = selectedCount;
  if (totCountEl) totCountEl.textContent = totalCount;

  const masterChk = document.getElementById("masterCheckbox");
  if (masterChk) {
    masterChk.checked = totalCount > 0 && selectedCount === totalCount;
    masterChk.indeterminate = selectedCount > 0 && selectedCount < totalCount;
  }

  const selectAllBtnText = document.getElementById("selectAllBtnText");
  if (selectAllBtnText) {
    selectAllBtnText.textContent = (selectedCount === totalCount && totalCount > 0) ? "Deselect All" : "Select All";
  }

  const hasSelection = selectedCount > 0;
  const exportBtn = document.getElementById("btnExportExcel");
  const copyBtn = document.getElementById("btnCopyTsv");
  const deepBtn = document.getElementById("btnDeepScrape");
  const delBtn = document.getElementById("btnDeleteSelected");
  const delText = document.getElementById("deleteSelectedBtnText");

  // Export Excel is enabled whenever there are rows in the table
  if (exportBtn) exportBtn.disabled = totalCount === 0;
  if (copyBtn) copyBtn.disabled = !hasSelection;
  if (deepBtn) deepBtn.disabled = !hasSelection;
  if (delBtn) delBtn.disabled = !hasSelection;
  if (delText) delText.textContent = selectedCount > 0 ? `Delete (${selectedCount})` : "Delete";

  // Check if dataset is customized (rows or columns deleted)
  const btnRestore = document.getElementById("btnRestoreTable");
  if (btnRestore) {
    const isCustomized = state.originalHeaders.length > 0 && (
      state.headers.length !== state.originalHeaders.length ||
      state.rows.length !== state.originalRows.length
    );
    btnRestore.style.display = isCustomized ? "inline-flex" : "none";
  }
}

// ============================================================================
// COPY & DELETE OPERATIONS (Single Row, Single Column, Multiple Selection)
// ============================================================================

// 1. Copy Individual Row
async function copyRow(rowIdx) {
  if (rowIdx < 0 || rowIdx >= state.rows.length) return;
  const row = state.rows[rowIdx];
  const tsv = state.headers.join("\t") + "\n" + row.join("\t");

  if (navigator.clipboard) {
    await navigator.clipboard.writeText(tsv);
    showToast(`Copied row #${rowIdx + 1}! Paste directly into Excel.`, "success");
    addLog("SUCCESS", `Copied student row #${rowIdx + 1} to clipboard.`, "TSV formatted with headers.");
  } else {
    showToast("Clipboard write permission unavailable.", "error");
  }
}

// 2. Copy Individual Column
async function copyColumn(colIdx) {
  if (colIdx < 0 || colIdx >= state.headers.length) return;
  const colName = state.headers[colIdx];
  const values = [colName].concat(state.rows.map(r => r[colIdx] || ""));
  const text = values.join("\n");

  if (navigator.clipboard) {
    await navigator.clipboard.writeText(text);
    showToast(`Copied column "${colName}" (${state.rows.length} rows)!`, "success");
    addLog("SUCCESS", `Copied column "${colName}" (${state.rows.length} rows) to clipboard.`, "Single column values.");
  } else {
    showToast("Clipboard write permission unavailable.", "error");
  }
}

// 3. Delete Individual Row
function deleteRow(rowIdx) {
  if (rowIdx < 0 || rowIdx >= state.rows.length) return;
  state.rows.splice(rowIdx, 1);

  // Re-index selected set
  const newSet = new Set();
  state.selectedIndices.forEach(idx => {
    if (idx < rowIdx) newSet.add(idx);
    else if (idx > rowIdx) newSet.add(idx - 1);
  });
  state.selectedIndices = newSet;

  renderRealTable(state.headers, state.rows, false);
  showToast("Row deleted. (Excel export will exclude it)", "info");
  addLog("ACTION", `Deleted row #${rowIdx + 1} from working table.`, "Customizing data for export.");
}

// 4. Delete Multiple Selected Rows
function deleteSelectedRows() {
  const count = state.selectedIndices.size;
  if (count === 0) {
    showToast("No rows selected to delete.", "error");
    return;
  }

  state.rows = state.rows.filter((_, idx) => !state.selectedIndices.has(idx));
  state.selectedIndices.clear();
  state.lastClickedRowIndex = null;
  // Automatically select all remaining rows so user can immediately export
  state.rows.forEach((_, idx) => state.selectedIndices.add(idx));

  renderRealTable(state.headers, state.rows, false);
  showToast(`Deleted ${count} selected row(s). ${state.rows.length} customized rows ready for Excel export.`, "info");
  addLog("ACTION", `Deleted ${count} selected rows from working table.`, "User customized dataset for Excel export.");
}

// 5. Delete Individual Column
function deleteColumn(colIdx) {
  if (colIdx < 0 || colIdx >= state.headers.length) return;
  const colName = state.headers[colIdx];

  state.headers.splice(colIdx, 1);
  state.rows.forEach(r => {
    r.splice(colIdx, 1);
  });

  renderRealTable(state.headers, state.rows, false);
  showToast(`Deleted column "${colName}". (Excel export will exclude it)`, "info");
  addLog("ACTION", `Deleted column "${colName}" from working table.`, "Customized columns for export.");
}

// 6. Restore Original Portal Table
function restoreOriginalTable() {
  if (!state.originalHeaders || state.originalHeaders.length === 0) return;
  state.headers = JSON.parse(JSON.stringify(state.originalHeaders));
  state.rows = JSON.parse(JSON.stringify(state.originalRows));
  state.selectedIndices = new Set();
  state.rows.forEach((_, idx) => state.selectedIndices.add(idx));

  renderRealTable(state.headers, state.rows, false);
  showToast("Restored all original rows and columns from portal.", "success");
  addLog("INFO", "Restored full original table dataset from portal.", "Reset custom row/column deletions.");
}

// Search Filter
function filterTable() {
  const query = (document.getElementById("tableSearchInput").value || "").toLowerCase().trim();
  state.rows.forEach((row, idx) => {
    const tr = document.getElementById(`row-${idx}`);
    if (!tr) return;
    if (!query) {
      tr.style.display = "";
      return;
    }
    const match = row.some(cell => String(cell).toLowerCase().includes(query));
    tr.style.display = match ? "" : "none";
  });
}

// Real Deep Profile Scraping on Live Portal
async function deepScrapeSelected() {
  const selectedArray = Array.from(state.selectedIndices).sort((a, b) => a - b);
  if (selectedArray.length === 0) {
    showToast("Please select at least one student row.", "error");
    return;
  }

  const btn = document.getElementById("btnDeepScrape");
  btn.disabled = true;
  addLog("ACTION", `Initiating live deep profile scraping for ${selectedArray.length} student(s)...`, "Sequential profile form extraction on live portal.");
  updateFloatingStatus(`Deep scraping ${selectedArray.length} student profiles...`);
  showToast(`Deep scraping ${selectedArray.length} student profiles on portal...`, "info");

  try {
    const res = await callBackend("deep-scrape", "POST", { indices: selectedArray });
    if (res && res.success) {
      showToast(`Scraped profile forms for ${res.processed_count} students!`, "success");
      updateFloatingStatus(`Completed deep scrape for ${res.processed_count} students`);
      await detectStudentTable();
    } else {
      addLog("WARNING", "Deep scrape completed with notice.", res ? res.message : "Process finished.");
    }
  } catch (e) {
    addLog("ERROR", `Deep scrape error: ${e}`, "Exception during deep scrape.");
  } finally {
    btn.disabled = false;
  }
}

// Real Excel (.xlsx) Download with Customized Data
async function exportToExcel() {
  if (!state.rows || state.rows.length === 0) {
    showToast("No student records available to export.", "error");
    return;
  }

  const selectedArray = Array.from(state.selectedIndices).sort((a, b) => a - b);
  // If specific rows selected, export those. If none selected, export ALL remaining customized rows!
  const selectedRows = selectedArray.length > 0 ? selectedArray.map(idx => state.rows[idx]) : state.rows;
  const sessionText = document.getElementById("sessionSelect")?.value || "2024-25";
  const classText = document.getElementById("classSelect")?.value || "Class";

  addLog("ACTION", `Generating customized Excel file for ${selectedRows.length} student entries (${state.headers.length} columns)...`, "Triggered openpyxl Excel generation.");
  updateFloatingStatus(`Generating Excel spreadsheet for ${selectedRows.length} students...`);
  showToast("Generating customized Excel spreadsheet...", "info");

  try {
    const response = await fetch("/api/export-excel", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        headers: state.headers,
        rows: selectedRows,
        sessionName: sessionText,
        className: classText
      })
    });

    if (response.ok) {
      const blob = await response.blob();
      const downloadUrl = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = downloadUrl;
      const cleanSession = sessionText.replace(/[^a-zA-Z0-9]/g, '_');
      const cleanClass = classText.replace(/[^a-zA-Z0-9]/g, '_');
      a.download = `PSP_Student_Profiles_${cleanSession}_${cleanClass}.xlsx`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);

      addLog("SUCCESS", `Downloaded customized Excel file (${selectedRows.length} rows, ${state.headers.length} columns).`, "Applied Signal Blue (#0057FF) header fill and customized dataset.");
      updateFloatingStatus(`Downloaded Excel file (${selectedRows.length} rows)`);
      showToast(`Downloaded ${selectedRows.length} customized records in Excel!`, "success");
    } else {
      const err = await response.json();
      addLog("ERROR", `Excel export failed: ${err.error || "Server error"}`, "Server failed to generate workbook.");
      showToast("Excel export failed.", "error");
    }
  } catch (e) {
    addLog("ERROR", `Excel download error: ${e}`, "Network or API failure.");
  }
}

// Copy to Clipboard (TSV of Selected Rows)
async function copyToClipboard() {
  const selectedArray = Array.from(state.selectedIndices).sort((a, b) => a - b);
  if (selectedArray.length === 0) {
    showToast("No rows selected to copy.", "error");
    return;
  }

  const selectedRows = selectedArray.map(idx => state.rows[idx]);
  addLog("ACTION", `Formatting ${selectedRows.length} real student entries into Tab-Separated Values (TSV)...`, "User clicked Copy TSV.");

  const tsvText = state.headers.join("\t") + "\n" + selectedRows.map(r => r.join("\t")).join("\n");

  if (navigator.clipboard) {
    await navigator.clipboard.writeText(tsvText);
    addLog("SUCCESS", `Copied ${selectedRows.length} real records to clipboard.`, "TSV formatted and ready for instant paste into Excel or Google Sheets.");
    updateFloatingStatus(`Copied ${selectedRows.length} records to clipboard`);
    showToast(`Copied ${selectedRows.length} rows! Paste directly into Excel.`, "success");
  } else {
    showToast("Clipboard write permission unavailable.", "error");
  }
}

// Activity & Audit Log Stream
function addLog(level, message, reason) {
  const now = new Date();
  const timeStr = now.toTimeString().split(" ")[0];
  const entry = { time: timeStr, level: level.toUpperCase(), message: message, reason: reason };
  state.logEntries.push(entry);

  // Update Drawer Body if matches filter
  renderLogEntry(entry);

  const badge = document.getElementById("activityBadgeCount");
  if (badge) badge.textContent = state.logEntries.length;

  // Update floating status bar with the latest event
  updateFloatingStatus(`[${entry.time}] ${message}`);
}

function renderLogEntry(entry) {
  const terminalBody = document.getElementById("terminalBody");
  if (!terminalBody) return;

  if (state.currentLogFilter !== "ALL" && entry.level !== state.currentLogFilter) {
    return;
  }

  const div = document.createElement("div");
  div.className = `log-entry level-${entry.level}`;
  div.innerHTML = `
    <div class="log-header-line">
      <span class="log-time">[${entry.time}]</span>
      <span class="log-tag ${entry.level}">${entry.level}</span>
    </div>
    <div class="log-body">${escapeHtml(entry.message)}</div>
    ${entry.reason ? `<div class="log-reason-note">Reason: ${escapeHtml(entry.reason)}</div>` : ""}
  `;
  terminalBody.appendChild(div);
  terminalBody.scrollTop = terminalBody.scrollHeight;
}

function filterLogs(level) {
  state.currentLogFilter = level;

  // Update filter buttons
  document.querySelectorAll(".filter-chip").forEach(btn => {
    btn.classList.toggle("active", btn.textContent.toUpperCase() === level || (level === "ALL" && btn.textContent === "All"));
  });

  const tb = document.getElementById("terminalBody");
  if (!tb) return;
  tb.innerHTML = "";

  state.logEntries.forEach(entry => {
    renderLogEntry(entry);
  });
}

function clearLogs() {
  state.logEntries = [];
  const tb = document.getElementById("terminalBody");
  if (tb) tb.innerHTML = "";
  const bg = document.getElementById("activityBadgeCount");
  if (bg) bg.textContent = "0";
}

function copyLogs() {
  const text = state.logEntries.map(e => `[${e.time}] [${e.level}] ${e.message} | Reason: ${e.reason}`).join("\n");
  if (navigator.clipboard) {
    navigator.clipboard.writeText(text);
    showToast("Audit logs copied to clipboard.", "info");
  }
}

// Toast Notifications
function showToast(message, type = "info") {
  const toast = document.getElementById("toastNotification");
  const msgEl = document.getElementById("toastMessage");
  const iconEl = document.getElementById("toastIcon");
  if (!toast || !msgEl) return;

  msgEl.textContent = message;
  if (iconEl) {
    if (type === "success") iconEl.innerHTML = "&#10003;";
    else if (type === "error") iconEl.innerHTML = "&#9888;";
    else iconEl.innerHTML = "&#9432;";
  }

  toast.className = `toast ${type} show`;

  setTimeout(() => {
    toast.className = "toast";
  }, 3500);
}

// Continuous Status Polling from Playwright Backend
function startStatusPolling() {
  state.pollTimer = setInterval(async () => {
    try {
      const status = await callBackend("poll-status", "GET", { last_index: state.lastLogIndex });
      if (!status) return;

      if (status.login_detected) {
        if (!state.isLoggedIn) {
          state.isLoggedIn = true;
          state.schoolUser = status.school_user || "Active";
          
          const pill = document.getElementById("headerAuthPill");
          pill.className = "auth-status-pill authenticated";
          document.getElementById("headerStatusText").textContent = `School: ${state.schoolUser}`;
          document.getElementById("btnSwitchSchool").style.display = "inline-flex";
          document.getElementById("btnToggleLogin").style.display = "none";
        }
        if (status.school_name && status.school_name !== state.schoolName) {
          state.schoolName = status.school_name;
          updateSchoolNameUI(status.school_name);
        }
      }

      if (status.new_logs && status.new_logs.length > 0) {
        status.new_logs.forEach(logItem => {
          addLog(logItem.level, logItem.message, logItem.reason);
        });
        state.lastLogIndex = status.next_log_index;
      }

    } catch (e) {
      // Ignore background poll errors
    }
  }, 1500);
}

// Universal API Dispatcher
async function callBackend(endpoint, method = "GET", body = null) {
  const url = `/api/${endpoint}` + (method === "GET" && body ? `?${new URLSearchParams(body).toString()}` : "");
  const opts = { method: method, headers: { "Content-Type": "application/json" } };
  if (method === "POST" && body) opts.body = JSON.stringify(body);

  const res = await fetch(url, opts);
  return await res.json();
}

function escapeHtml(text) {
  if (!text) return "";
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
