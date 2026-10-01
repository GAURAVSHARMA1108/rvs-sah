/**
 * RajPSP Embeddable Widget SDK (widget.js)
 * Standalone, zero-dependency drop-in integration for third-party school ERPs and websites.
 * Features:
 * - Dynamic modal resizing for preview (compact login -> wide data selection)
 * - Row selection checkboxes (select all / individual students)
 * - Column selection customization (toggle columns to import)
 * - Real-time student search filter
 * - Sticky table headers with smooth full-height scrolling for 100+ records
 * - Scoped root rendering for both Modal Popup and Inline Container modes
 * Theme: Signal Blue (#0057FF) and Porcelain (#F8F7F4).
 */
(function(window) {
  'use strict';

  // Determine API base URL from script tag source
  let scriptOrigin = window.location.origin;
  const currentScript = document.currentScript;
  if (currentScript && currentScript.src) {
    try {
      const url = new URL(currentScript.src);
      scriptOrigin = url.origin;
    } catch (e) {}
  }

  const RajPSPWidget = {
    _config: {
      apiKey: '',
      apiUrl: scriptOrigin,
      triggerElement: null,
      mode: 'modal', // 'modal' or 'inline'
      container: null,
      onSuccess: null,
      onError: null
    },

    _state: {
      sessionId: null,
      isOpening: false,
      isLoadingSession: false,
      schoolCode: '',
      schoolName: '',
      selectedSession: '',
      selectedClass: '',
      sessions: [],
      classes: [],
      extractedData: null,
      // Column & Row selection state
      allHeaders: [],
      allRows: [],
      selectedColIndices: [], // Array of active column indices
      selectedRowIndices: new Set(), // Set of active row indices
      searchTerm: '',
      showColumnSelector: false
    },

    _activeRoot: null,

    init: function(options) {
      this._config = Object.assign({}, this._config, options);
      if (!this._config.apiKey) {
        console.error('[RajPSPWidget] Initialization Error: Missing mandatory `apiKey`.');
        return;
      }

      this._injectStyles();

      // Bind trigger element if provided
      if (this._config.triggerElement) {
        const triggers = document.querySelectorAll(this._config.triggerElement);
        triggers.forEach(el => {
          el.onclick = (e) => {
            e.preventDefault();
            this.open();
          };
        });
      }

      // If inline mode with container, render immediately
      if (this._config.mode === 'inline' && this._config.container) {
        this._renderInline();
      }
    },

    open: function() {
      if (this._state.isOpening) return;
      this._state.isOpening = true;

      if (this._config.mode === 'inline') {
        this._renderInline();
        this._state.isOpening = false;
      } else {
        this._renderModal();
        this._startSession().finally(() => {
          this._state.isOpening = false;
        });
      }
    },

    close: function() {
      this._state.isOpening = false;
      const overlay = document.getElementById('rajpsp-widget-overlay');
      if (overlay) {
        overlay.classList.remove('active');
        setTimeout(() => overlay.remove(), 250);
      }
      if (this._state.sessionId) {
        this._callApi('/session/close', 'POST', { session_id: this._state.sessionId }).catch(() => {});
        this._state.sessionId = null;
      }
    },

    // =========================================================================
    // API CALLS
    // =========================================================================

    _callApi: async function(endpoint, method = 'POST', body = null) {
      const url = `${this._config.apiUrl}/api/v1${endpoint}`;
      const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${this._config.apiKey}`,
        'X-API-Key': this._config.apiKey
      };
      const opts = { method: method, headers: headers };
      if (body) opts.body = JSON.stringify(body);

      const resp = await fetch(url, opts);
      let data = {};
      try {
        data = await resp.json();
      } catch (e) {
        data = { error: `Server returned status ${resp.status}` };
      }

      if (!resp.ok) {
        const error = new Error(data.error || data.detail || 'API Request failed');
        error.data = data;
        error.status = resp.status;
        throw error;
      }
      return data;
    },

    _startSession: async function() {
      if (this._state.isLoadingSession) return;
      this._state.isLoadingSession = true;
      this._showLoading('Connecting to live Rajasthan portal in background...');
      try {
        const res = await this._callApi('/session/start', 'POST');
        this._state.sessionId = res.session_id;
        this._hideLoading();
        this._renderLoginForm(res.captcha_b64);
      } catch (err) {
        const errMsg = err.message || 'Failed to initialize session';
        this._showError(errMsg);
        if (this._config.onError) this._config.onError(err);
      } finally {
        this._state.isLoadingSession = false;
      }
    },

    _refreshCaptcha: async function() {
      const img = this._query('.rajpsp-captcha-img');
      const loadSpan = this._query('.rajpsp-captcha-load');
      if (img) img.style.display = 'none';
      if (loadSpan) {
        loadSpan.style.display = 'inline';
        loadSpan.innerText = 'Loading...';
      }

      try {
        const res = await this._callApi('/session/refresh-captcha', 'POST', { session_id: this._state.sessionId });
        if (img) {
          img.src = res.captcha_b64;
          img.style.display = 'block';
        }
        if (loadSpan) loadSpan.style.display = 'none';
      } catch (err) {
        if (loadSpan) loadSpan.innerText = 'Failed. Retry.';
      }
    },

    _submitLogin: async function() {
      const userEl = this._query('.rajpsp-input-user');
      const pwdEl = this._query('.rajpsp-input-pwd');
      const capEl = this._query('.rajpsp-input-captcha');

      const code = userEl ? userEl.value.trim() : '';
      const pwd = pwdEl ? pwdEl.value.trim() : '';
      const captcha = capEl ? capEl.value.trim() : '';

      if (!code || !pwd || !captcha) {
        this._showBannerError('Please enter School PSP Code, Password, and CAPTCHA.');
        return;
      }

      const btn = this._query('.rajpsp-btn-login-submit');
      if (btn) {
        btn.disabled = true;
        btn.innerHTML = `<span class="rajpsp-spinner-inline"></span> Authenticating against portal...`;
      }
      this._hideBannerError();

      try {
        const res = await this._callApi('/session/login', 'POST', {
          session_id: this._state.sessionId,
          username: code,
          password: pwd,
          captcha: captcha
        });

        this._state.schoolCode = code;
        this._state.schoolName = res.school_name || code;
        this._state.sessions = res.sessions || [];
        this._state.classes = res.classes || [];

        this._renderDropdownSelection();
      } catch (err) {
        if (btn) {
          btn.disabled = false;
          btn.innerHTML = `Authenticate & Proceed &rarr;`;
        }
        const errMsg = err.message || 'Authentication failed. Please check credentials and CAPTCHA.';
        this._showBannerError(errMsg);
        if (capEl) {
          capEl.value = '';
          capEl.focus();
        }
        if (err.data && err.data.captcha_b64) {
          const img = this._query('.rajpsp-captcha-img');
          const loadSpan = this._query('.rajpsp-captcha-load');
          if (img) {
            img.src = err.data.captcha_b64;
            img.style.display = 'block';
          }
          if (loadSpan) loadSpan.style.display = 'none';
        } else {
          this._refreshCaptcha();
        }
      }
    },

    _fetchStudents: async function() {
      const sessEl = this._query('.rajpsp-select-session');
      const clsEl = this._query('.rajpsp-select-class');

      const sessVal = sessEl ? sessEl.value : '';
      const clsVal = clsEl ? clsEl.value : '';

      if (!sessVal || !clsVal) {
        this._showBannerError('Please select both Academic Session and Class.');
        return;
      }

      this._state.selectedSession = sessVal;
      this._state.selectedClass = clsVal;

      const btn = this._query('.rajpsp-btn-fetch-submit');
      if (btn) {
        btn.disabled = true;
        btn.innerHTML = `<span class="rajpsp-spinner-inline"></span> Extracting student records...`;
      }
      this._hideBannerError();

      try {
        const res = await this._callApi('/session/fetch-students', 'POST', {
          session_id: this._state.sessionId,
          school_code: this._state.schoolCode,
          session_val: sessVal,
          class_val: clsVal
        });

        this._state.extractedData = res;
        this._state.allHeaders = res.headers || [];
        this._state.allRows = res.rows || [];
        // Default: select all columns and all rows
        this._state.selectedColIndices = (res.headers || []).map((_, idx) => idx);
        this._state.selectedRowIndices = new Set((res.rows || []).map((_, idx) => idx));
        this._state.searchTerm = '';
        this._state.showColumnSelector = false;

        this._renderPreview();
      } catch (err) {
        if (btn) {
          btn.disabled = false;
          btn.innerHTML = `Extract Student Records &rarr;`;
        }
        this._showBannerError(err.message || 'Failed to extract students from portal.');
      }
    },

    // =========================================================================
    // UI SCOPED RENDERING
    // =========================================================================

    _query: function(selector) {
      if (!this._activeRoot) return document.querySelector(selector);
      return this._activeRoot.querySelector(selector);
    },

    _queryAll: function(selector) {
      if (!this._activeRoot) return Array.from(document.querySelectorAll(selector));
      return Array.from(this._activeRoot.querySelectorAll(selector));
    },

    _getBody: function() {
      return this._query('.rajpsp-modal-body');
    },

    _renderModal: function() {
      // Clean up previous overlay if present
      const old = document.getElementById('rajpsp-widget-overlay');
      if (old) old.remove();

      const overlay = document.createElement('div');
      overlay.id = 'rajpsp-widget-overlay';
      overlay.className = 'rajpsp-overlay';
      overlay.innerHTML = `
        <div class="rajpsp-modal">
          <div class="rajpsp-modal-header">
            <div class="rajpsp-brand">
              <span class="rajpsp-badge">RVS SAH</span>
              <span class="rajpsp-title">Student Import Assistant</span>
            </div>
            <button class="rajpsp-close-btn" type="button" onclick="RajPSPWidget.close()">&times;</button>
          </div>
          <div class="rajpsp-modal-body"></div>
        </div>
      `;
      document.body.appendChild(overlay);
      this._activeRoot = overlay;
      setTimeout(() => overlay.classList.add('active'), 10);
    },

    _renderInline: function() {
      const container = document.querySelector(this._config.container);
      if (!container) return;

      // Close modal if open
      const oldModal = document.getElementById('rajpsp-widget-overlay');
      if (oldModal) oldModal.remove();

      container.innerHTML = `
        <div class="rajpsp-inline-card">
          <div class="rajpsp-modal-header">
            <div class="rajpsp-brand">
              <span class="rajpsp-badge">RVS SAH</span>
              <span class="rajpsp-title">Student Import Assistant</span>
            </div>
          </div>
          <div class="rajpsp-modal-body"></div>
        </div>
      `;
      this._activeRoot = container;
      this._startSession();
    },

    _showBannerError: function(msg) {
      const el = this._query('.rajpsp-banner-error');
      if (el) {
        el.innerText = msg;
        el.style.display = 'block';
      } else {
        this._showError(msg);
      }
    },

    _hideBannerError: function() {
      const el = this._query('.rajpsp-banner-error');
      if (el) {
        el.style.display = 'none';
        el.innerText = '';
      }
    },

    _showLoading: function(text) {
      const body = this._getBody();
      if (body) {
        body.innerHTML = `
          <div class="rajpsp-loader-wrap">
            <div class="rajpsp-spinner"></div>
            <p>${text}</p>
          </div>
        `;
      }
    },

    _hideLoading: function() {},

    _showError: function(msg) {
      const body = this._getBody();
      if (body) {
        body.innerHTML = `
          <div style="padding: 12px 0;">
            <div class="rajpsp-alert-error" style="display:flex; align-items:flex-start; gap:10px; padding:12px; margin-bottom:14px; border-radius:8px;">
              <span style="font-size:20px; line-height:1;">⚠️</span>
              <div>
                <strong style="display:block; margin-bottom:4px; font-size:13px; color:#B91C1C;">Connection / Plan Notice</strong>
                <span style="color:#7F1D1D; font-size:12px; line-height:1.4;">${msg}</span>
              </div>
            </div>
            <div style="display:flex; justify-content:flex-end; gap:8px;">
              <button class="rajpsp-btn-secondary" type="button" onclick="RajPSPWidget._startSession()">↻ Retry Connection</button>
              ${this._config.mode === 'modal' ? '<button class="rajpsp-btn-secondary" type="button" onclick="RajPSPWidget.close()">Dismiss</button>' : ''}
            </div>
          </div>
        `;
      }
    },

    _renderLoginForm: function(captchaB64) {
      const body = this._getBody();
      if (!body) return;

      body.classList.remove('rajpsp-body-preview');
      const modal = this._query('.rajpsp-modal') || this._query('.rajpsp-inline-card');
      if (modal) modal.classList.remove('rajpsp-modal-wide');

      body.innerHTML = `
        <div class="rajpsp-form-group">
          <div class="rajpsp-banner-error rajpsp-alert-error" style="display:none;"></div>
          <p class="rajpsp-subtitle">Enter your School credentials to extract student data directly into your app.</p>
          
          <div class="rajpsp-field">
            <label>School PSP Code</label>
            <input type="text" class="rajpsp-input-user" placeholder="e.g. P25814" autocomplete="username">
          </div>

          <div class="rajpsp-field">
            <label>School Password</label>
            <input type="password" class="rajpsp-input-pwd" placeholder="Enter password" autocomplete="current-password">
          </div>

          <div class="rajpsp-field">
            <label>Live Portal CAPTCHA</label>
            <div class="rajpsp-captcha-row">
              <div class="rajpsp-captcha-box">
                <span class="rajpsp-captcha-load" style="${captchaB64 ? 'display:none;' : ''}">Loading...</span>
                <img class="rajpsp-captcha-img" src="${captchaB64 || ''}" style="${captchaB64 ? 'display:block;' : 'display:none;'}">
              </div>
              <button class="rajpsp-btn-refresh" type="button" onclick="RajPSPWidget._refreshCaptcha()" title="Refresh Captcha">↻</button>
              <input type="text" class="rajpsp-input-captcha" placeholder="Captcha" maxlength="10">
            </div>
          </div>

          <button class="rajpsp-btn-primary rajpsp-btn-login-submit" type="button" onclick="RajPSPWidget._submitLogin()">
            Authenticate & Proceed &rarr;
          </button>
        </div>
      `;
    },

    _renderDropdownSelection: function() {
      const body = this._getBody();
      if (!body) return;

      body.classList.remove('rajpsp-body-preview');
      const modal = this._query('.rajpsp-modal') || this._query('.rajpsp-inline-card');
      if (modal) modal.classList.remove('rajpsp-modal-wide');

      const sessOpts = this._state.sessions.map(s => `<option value="${s.value}">${s.text}</option>`).join('');
      const clsOpts = this._state.classes.map(c => `<option value="${c.value}">${c.text}</option>`).join('');

      body.innerHTML = `
        <div class="rajpsp-form-group">
          <div class="rajpsp-banner-error rajpsp-alert-error" style="display:none;"></div>
          <div class="rajpsp-auth-pill">
            ✓ Authenticated: <strong>${this._state.schoolName}</strong>
          </div>
          <p class="rajpsp-subtitle">Select Academic Session and Class to extract records:</p>

          <div class="rajpsp-field">
            <label>Academic Session</label>
            <select class="rajpsp-select-session">${sessOpts || '<option value="">-- No Sessions Found --</option>'}</select>
          </div>

          <div class="rajpsp-field">
            <label>Class</label>
            <select class="rajpsp-select-class">${clsOpts || '<option value="">-- No Classes Found --</option>'}</select>
          </div>

          <button class="rajpsp-btn-primary rajpsp-btn-fetch-submit" type="button" onclick="RajPSPWidget._fetchStudents()">
            Extract Student Records &rarr;
          </button>
        </div>
      `;
    },

    // =========================================================================
    // DATA PREVIEW & SELECTION (ROW & COLUMN CUSTOMIZATION)
    // =========================================================================

    _renderPreview: function() {
      const body = this._getBody();
      if (!body) return;

      body.classList.add('rajpsp-body-preview');
      // Expand modal container to full wide view
      const modal = this._query('.rajpsp-modal') || this._query('.rajpsp-inline-card');
      if (modal) modal.classList.add('rajpsp-modal-wide');

      const headers = this._state.allHeaders || [];
      const rows = this._state.allRows || [];
      const count = rows.length;

      if (count === 0) {
        body.innerHTML = `
          <div class="rajpsp-form-group">
            <p class="rajpsp-subtitle">No student records found on the portal for this selection.</p>
            <button class="rajpsp-btn-secondary" type="button" onclick="RajPSPWidget._renderDropdownSelection()">
              &larr; Back to Selection
            </button>
          </div>
        `;
        return;
      }

      // Filter rows based on search term
      const term = (this._state.searchTerm || '').toLowerCase().trim();
      const visibleRowIndices = [];
      for (let i = 0; i < rows.length; i++) {
        if (!term) {
          visibleRowIndices.push(i);
        } else {
          const rowText = rows[i].join(' ').toLowerCase();
          if (rowText.includes(term)) {
            visibleRowIndices.push(i);
          }
        }
      }

      const activeColIndices = this._state.selectedColIndices || [];
      const selectedRowCount = this._state.selectedRowIndices.size;
      const isAllVisibleSelected = visibleRowIndices.length > 0 && visibleRowIndices.every(idx => this._state.selectedRowIndices.has(idx));

      // Build Column Selector Drawer/Popover
      let columnSelectorHtml = '';
      if (this._state.showColumnSelector) {
        const colPills = headers.map((h, colIdx) => {
          const isChecked = activeColIndices.includes(colIdx);
          return `
            <label class="rajpsp-col-pill ${isChecked ? 'active' : ''}">
              <input type="checkbox" ${isChecked ? 'checked' : ''} onchange="RajPSPWidget._toggleColumn(${colIdx}, this.checked)">
              <span>${this._escapeHtml(h)}</span>
            </label>
          `;
        }).join('');

        columnSelectorHtml = `
          <div class="rajpsp-col-panel">
            <div class="rajpsp-col-panel-header">
              <span>Choose Columns to Import (${activeColIndices.length} of ${headers.length}):</span>
              <div class="rajpsp-col-panel-actions">
                <button type="button" onclick="RajPSPWidget._selectAllColumns(true)">Select All</button>
                <span>|</span>
                <button type="button" onclick="RajPSPWidget._selectAllColumns(false)">Clear</button>
              </div>
            </div>
            <div class="rajpsp-col-pills-wrap">
              ${colPills}
            </div>
          </div>
        `;
      }

      // Build Table Header
      const thHtml = [
        `<th style="width: 44px; text-align: center;">
          <input type="checkbox" title="Select All Visible" ${isAllVisibleSelected ? 'checked' : ''} onchange="RajPSPWidget._toggleSelectAllVisible(this.checked)">
        </th>`,
        ...activeColIndices.map(colIdx => `<th>${this._escapeHtml(headers[colIdx])}</th>`)
      ].join('');

      // Build Table Rows
      let trHtml = '';
      if (visibleRowIndices.length === 0) {
        trHtml = `<tr><td colspan="${activeColIndices.length + 1}" style="text-align:center; padding: 24px; color:#64748B;">No students matching "${this._escapeHtml(this._state.searchTerm)}"</td></tr>`;
      } else {
        trHtml = visibleRowIndices.map(rowIdx => {
          const rowData = rows[rowIdx];
          const isRowChecked = this._state.selectedRowIndices.has(rowIdx);
          const tdCols = activeColIndices.map(colIdx => `<td>${this._escapeHtml(rowData[colIdx] || '')}</td>`).join('');
          return `
            <tr class="${isRowChecked ? 'selected' : ''}" onclick="RajPSPWidget._onRowClick(event, ${rowIdx})">
              <td style="text-align: center;" onclick="event.stopPropagation()">
                <input type="checkbox" ${isRowChecked ? 'checked' : ''} onchange="RajPSPWidget._toggleRow(${rowIdx}, this.checked)">
              </td>
              ${tdCols}
            </tr>
          `;
        }).join('');
      }

      body.innerHTML = `
        <div class="rajpsp-preview-wrap">
          <!-- Top Bar: Info + Search + Column Customization -->
          <div class="rajpsp-preview-toolbar">
            <div class="rajpsp-preview-meta">
              <span class="rajpsp-badge-count">🎉 Extracted <strong>${count} Records</strong></span>
              <span class="rajpsp-selected-pill">Selected: <strong>${selectedRowCount}</strong> of ${count} Students</span>
            </div>

            <div class="rajpsp-preview-tools">
              <div class="rajpsp-search-wrap">
                <input type="text" class="rajpsp-search-input" placeholder="🔍 Search name, ID, father..." value="${this._escapeHtml(this._state.searchTerm)}" oninput="RajPSPWidget._onSearch(this.value)">
                <button type="button" class="rajpsp-search-clear" onclick="RajPSPWidget._onSearch('')" style="${this._state.searchTerm ? 'display:block;' : 'display:none;'}">&times;</button>
              </div>

              <button type="button" class="rajpsp-btn-tool ${this._state.showColumnSelector ? 'active' : ''}" onclick="RajPSPWidget._toggleColumnSelector()">
                ⚙️ Columns (${activeColIndices.length}/${headers.length}) ▾
              </button>
            </div>
          </div>

          ${columnSelectorHtml}

          <!-- Full Table Container with Sticky Headers & Full Scroll -->
          <div class="rajpsp-preview-scroll">
            <table class="rajpsp-table">
              <thead><tr>${thHtml}</tr></thead>
              <tbody>${trHtml}</tbody>
            </table>
          </div>

          <!-- Bottom Footer Bar -->
          <div class="rajpsp-preview-footer">
            <div class="rajpsp-footer-tip">
              💡 Tip: Click checkboxes to exclude specific students or columns from import.
            </div>

            <div class="rajpsp-actions-row">
              <button class="rajpsp-btn-primary ${selectedRowCount === 0 || activeColIndices.length === 0 ? 'disabled' : ''}" type="button" onclick="RajPSPWidget._confirmImport()">
                Import ${selectedRowCount} Selected Students into System &rarr;
              </button>
              <button class="rajpsp-btn-secondary" type="button" onclick="RajPSPWidget._renderDropdownSelection()">
                &larr; Back
              </button>
            </div>
          </div>
        </div>
      `;
    },

    _onSearch: function(val) {
      this._state.searchTerm = val;
      const input = this._query('.rajpsp-search-input');
      if (input && input.value !== val) input.value = val;

      const clearBtn = this._query('.rajpsp-search-clear');
      if (clearBtn) clearBtn.style.display = val ? 'block' : 'none';

      const term = (val || '').toLowerCase().trim();
      const rows = this._state.allRows || [];
      const tbody = this._query('.rajpsp-table tbody');
      if (!tbody) return;

      const trs = tbody.querySelectorAll('tr');
      let visibleCount = 0;
      let visibleSelectedCount = 0;

      for (let i = 0; i < rows.length; i++) {
        const rowText = rows[i].join(' ').toLowerCase();
        const matches = !term || rowText.includes(term);
        const tr = trs[i];
        if (tr) {
          tr.style.display = matches ? '' : 'none';
          if (matches) {
            visibleCount++;
            if (this._state.selectedRowIndices.has(i)) {
              visibleSelectedCount++;
            }
          }
        }
      }

      const masterCb = this._query('thead input[type="checkbox"]');
      if (masterCb) {
        masterCb.checked = visibleCount > 0 && visibleSelectedCount === visibleCount;
      }
    },

    _toggleColumnSelector: function() {
      this._state.showColumnSelector = !this._state.showColumnSelector;
      this._renderPreview();
    },

    _toggleColumn: function(colIdx, isChecked) {
      if (isChecked) {
        if (!this._state.selectedColIndices.includes(colIdx)) {
          this._state.selectedColIndices.push(colIdx);
          this._state.selectedColIndices.sort((a, b) => a - b);
        }
      } else {
        this._state.selectedColIndices = this._state.selectedColIndices.filter(i => i !== colIdx);
      }
      this._renderPreview();
    },

    _selectAllColumns: function(selectAll) {
      if (selectAll) {
        this._state.selectedColIndices = this._state.allHeaders.map((_, i) => i);
      } else {
        this._state.selectedColIndices = [];
      }
      this._renderPreview();
    },

    _toggleRow: function(rowIdx, isChecked) {
      if (isChecked) {
        this._state.selectedRowIndices.add(rowIdx);
      } else {
        this._state.selectedRowIndices.delete(rowIdx);
      }
      this._updateRowSelectionUi();
    },

    _onRowClick: function(e, rowIdx) {
      // Toggle row selection on row click unless clicked an input/button
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'BUTTON' || e.target.tagName === 'A') return;
      if (this._state.selectedRowIndices.has(rowIdx)) {
        this._state.selectedRowIndices.delete(rowIdx);
      } else {
        this._state.selectedRowIndices.add(rowIdx);
      }
      this._updateRowSelectionUi();
    },

    _toggleSelectAllVisible: function(isChecked) {
      const term = (this._state.searchTerm || '').toLowerCase().trim();
      const rows = this._state.allRows || [];
      for (let i = 0; i < rows.length; i++) {
        if (!term || rows[i].join(' ').toLowerCase().includes(term)) {
          if (isChecked) {
            this._state.selectedRowIndices.add(i);
          } else {
            this._state.selectedRowIndices.delete(i);
          }
        }
      }
      this._updateRowSelectionUi();
    },

    _updateRowSelectionUi: function() {
      const tbody = this._query('.rajpsp-table tbody');
      if (tbody) {
        const trs = tbody.querySelectorAll('tr');
        for (let i = 0; i < trs.length; i++) {
          const isSelected = this._state.selectedRowIndices.has(i);
          trs[i].classList.toggle('selected', isSelected);
          const cb = trs[i].querySelector('input[type="checkbox"]');
          if (cb) cb.checked = isSelected;
        }
      }
      const count = (this._state.allRows || []).length;
      const selCount = this._state.selectedRowIndices.size;
      const pill = this._query('.rajpsp-selected-pill');
      if (pill) pill.innerHTML = `Selected: <strong>${selCount}</strong> of ${count} Students`;

      const importBtn = this._query('.rajpsp-actions-row .rajpsp-btn-primary');
      if (importBtn) {
        importBtn.innerText = `Import ${selCount} Selected Students into System \u2192`;
        if (selCount === 0 || (this._state.selectedColIndices || []).length === 0) {
          importBtn.classList.add('disabled');
        } else {
          importBtn.classList.remove('disabled');
        }
      }

      const term = (this._state.searchTerm || '').toLowerCase().trim();
      const rows = this._state.allRows || [];
      let visibleCount = 0;
      let visibleSelectedCount = 0;
      for (let i = 0; i < rows.length; i++) {
        if (!term || rows[i].join(' ').toLowerCase().includes(term)) {
          visibleCount++;
          if (this._state.selectedRowIndices.has(i)) visibleSelectedCount++;
        }
      }
      const masterCb = this._query('thead input[type="checkbox"]');
      if (masterCb) {
        masterCb.checked = visibleCount > 0 && visibleSelectedCount === visibleCount;
      }
    },

    _confirmImport: function() {
      const activeColIndices = this._state.selectedColIndices || [];
      const selectedRowIndices = Array.from(this._state.selectedRowIndices || []).sort((a, b) => a - b);

      if (selectedRowIndices.length === 0) {
        alert('Please select at least 1 student record to import.');
        return;
      }
      if (activeColIndices.length === 0) {
        alert('Please select at least 1 column to import.');
        return;
      }

      const allHeaders = this._state.allHeaders || [];
      const allRows = this._state.allRows || [];

      // Extract active headers
      const chosenHeaders = activeColIndices.map(colIdx => allHeaders[colIdx]);

      // Extract active rows with active columns only
      const filteredStudents = selectedRowIndices.map(rowIdx => {
        const fullRow = allRows[rowIdx] || [];
        return activeColIndices.map(colIdx => fullRow[colIdx] || '');
      });

      if (this._config.onSuccess) {
        this._config.onSuccess({
          success: true,
          school_code: this._state.schoolCode,
          school_name: this._state.schoolName,
          session: this._state.selectedSession,
          class_name: this._state.selectedClass,
          count: filteredStudents.length,
          total_extracted: allRows.length,
          headers: chosenHeaders,
          students: filteredStudents,
          quota_remaining: this._state.extractedData ? this._state.extractedData.quota_remaining : undefined
        });
      }
      this.close();
    },

    _escapeHtml: function(str) {
      if (str === null || str === undefined) return '';
      return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
    },

    _injectStyles: function() {
      if (document.getElementById('rajpsp-widget-styles')) return;
      const style = document.createElement('style');
      style.id = 'rajpsp-widget-styles';
      style.textContent = `
        .rajpsp-overlay {
          position: fixed; top: 0; left: 0; width: 100vw; height: 100vh;
          background: rgba(15, 23, 42, 0.65); backdrop-filter: blur(4px);
          display: flex; align-items: center; justify-content: center;
          padding: 16px; box-sizing: border-box; overflow-y: auto;
          z-index: 999999; opacity: 0; pointer-events: none; transition: opacity 0.2s ease;
          font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        }
        .rajpsp-overlay.active { opacity: 1; pointer-events: auto; }
        .rajpsp-modal, .rajpsp-inline-card {
          background: #FFFFFF; width: 92%; max-width: 540px; border-radius: 12px;
          box-shadow: 0 20px 40px rgba(0, 0, 0, 0.2); overflow: hidden; border: 1px solid #DCD8CB;
          display: flex; flex-direction: column;
          max-height: calc(100vh - 32px);
          margin: auto;
          transition: max-width 0.3s cubic-bezier(0.16, 1, 0.3, 1), width 0.3s ease;
        }
        .rajpsp-modal.rajpsp-modal-wide {
          max-width: 1160px;
          width: 95vw;
          max-height: calc(100vh - 32px);
        }
        .rajpsp-inline-card.rajpsp-modal-wide {
          max-width: 100%;
          width: 100%;
        }
        .rajpsp-modal-header {
          background: #F8F7F4; border-bottom: 1px solid #EBE8DE; padding: 12px 18px;
          display: flex; align-items: center; justify-content: space-between;
          flex-shrink: 0;
        }
        .rajpsp-brand { display: flex; align-items: center; gap: 8px; }
        .rajpsp-badge {
          background: #0057FF; color: #fff; font-size: 11px; font-weight: 700;
          padding: 2px 7px; border-radius: 4px; text-transform: uppercase;
        }
        .rajpsp-title { font-size: 14px; font-weight: 700; color: #0F172A; }
        .rajpsp-close-btn {
          background: none; border: none; font-size: 22px; cursor: pointer; color: #94A3B8;
        }
        .rajpsp-close-btn:hover { color: #EF4444; }
        .rajpsp-modal-body {
          padding: 16px 20px;
          display: flex; flex-direction: column;
          flex: 1 1 auto; min-height: 0; overflow-y: auto;
        }
        .rajpsp-modal-body.rajpsp-body-preview {
          padding: 12px 18px;
          overflow-y: hidden;
        }
        .rajpsp-preview-wrap {
          display: flex; flex-direction: column;
          height: 100%; flex: 1 1 auto; min-height: 0;
        }
        .rajpsp-subtitle { font-size: 13px; color: #475569; margin-bottom: 14px; line-height: 1.4; }
        .rajpsp-field { margin-bottom: 12px; display: flex; flex-direction: column; gap: 4px; }
        .rajpsp-field label { font-size: 12px; font-weight: 600; color: #0F172A; }
        .rajpsp-field input, .rajpsp-field select {
          padding: 8px 12px; border: 1px solid #DCD8CB; border-radius: 6px;
          font-size: 13px; outline: none; transition: border-color 0.2s;
        }
        .rajpsp-field input:focus, .rajpsp-field select:focus { border-color: #0057FF; }
        .rajpsp-captcha-row { display: flex; gap: 8px; align-items: center; }
        .rajpsp-captcha-box {
          height: 38px; width: 130px; border: 1px solid #BCD4FF; border-radius: 6px;
          background: #F2F7FF; display: flex; align-items: center; justify-content: center;
          overflow: hidden;
        }
        .rajpsp-captcha-box img { height: 100%; width: 100%; object-fit: contain; }
        .rajpsp-btn-refresh {
          height: 38px; width: 38px; background: #F1EFEA; border: 1px solid #DCD8CB;
          border-radius: 6px; cursor: pointer; font-size: 16px;
        }
        .rajpsp-btn-primary {
          width: 100%; background: #0057FF; color: #fff; border: none; padding: 10px 16px;
          border-radius: 6px; font-weight: 600; font-size: 14px; cursor: pointer;
          margin-top: 8px; transition: background 0.2s;
        }
        .rajpsp-btn-primary:hover { background: #0045D6; }
        .rajpsp-btn-primary.disabled {
          opacity: 0.5; cursor: not-allowed; pointer-events: none;
        }
        .rajpsp-btn-secondary {
          background: #F1EFEA; color: #475569; border: 1px solid #DCD8CB; padding: 8px 14px;
          border-radius: 6px; font-weight: 600; font-size: 13px; cursor: pointer;
        }
        .rajpsp-alert-error {
          background: #FEF2F2; color: #EF4444; border: 1px solid #FECACA;
          padding: 8px 12px; border-radius: 6px; font-size: 12px; margin-bottom: 12px;
        }
        .rajpsp-auth-pill {
          background: #ECFDF5; color: #10B981; border: 1px solid #A7F3D0;
          padding: 8px 12px; border-radius: 6px; font-size: 13px; margin-bottom: 14px;
        }
        .rajpsp-actions-row { display: flex; gap: 8px; align-items: center; }
        .rajpsp-loader-wrap {
          display: flex; flex-direction: column; align-items: center; justify-content: center;
          padding: 30px 10px; gap: 12px; color: #475569; font-size: 13px;
        }
        .rajpsp-spinner {
          width: 32px; height: 32px; border: 3px solid #EBF2FF;
          border-top-color: #0057FF; border-radius: 50%; animation: rajpsp-spin 0.8s linear infinite;
        }
        .rajpsp-spinner-inline {
          display: inline-block; width: 14px; height: 14px;
          border: 2px solid rgba(255,255,255,0.4); border-top-color: #fff;
          border-radius: 50%; animation: rajpsp-spin 0.6s linear infinite;
          vertical-align: -2px; margin-right: 6px;
        }
        @keyframes rajpsp-spin { to { transform: rotate(360deg); } }

        /* Preview Toolbar */
        .rajpsp-preview-toolbar {
          display: flex; align-items: center; justify-content: space-between;
          flex-wrap: wrap; gap: 8px; margin-bottom: 8px; padding-bottom: 8px;
          border-bottom: 1px solid #EBE8DE; flex-shrink: 0;
        }
        .rajpsp-preview-meta { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
        .rajpsp-badge-count {
          background: #ECFDF5; color: #059669; font-size: 12px; font-weight: 600;
          padding: 4px 9px; border-radius: 6px; border: 1px solid #A7F3D0;
        }
        .rajpsp-selected-pill {
          font-size: 12px; color: #475569; background: #F1EFEA;
          padding: 4px 9px; border-radius: 6px; border: 1px solid #DCD8CB;
        }
        .rajpsp-preview-tools { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
        .rajpsp-search-wrap { position: relative; display: flex; align-items: center; }
        .rajpsp-search-input {
          padding: 6px 26px 6px 10px; border: 1px solid #DCD8CB; border-radius: 6px;
          font-size: 12px; outline: none; width: 190px; transition: border-color 0.2s, width 0.2s;
        }
        .rajpsp-search-input:focus { border-color: #0057FF; width: 230px; }
        .rajpsp-search-clear {
          position: absolute; right: 6px; background: none; border: none;
          font-size: 14px; color: #94A3B8; cursor: pointer;
        }
        .rajpsp-btn-tool {
          background: #FFFFFF; border: 1px solid #DCD8CB; padding: 6px 12px;
          border-radius: 6px; font-size: 12px; font-weight: 600; color: #334155;
          cursor: pointer; display: flex; align-items: center; gap: 4px; transition: all 0.2s;
        }
        .rajpsp-btn-tool:hover, .rajpsp-btn-tool.active {
          background: #F2F7FF; border-color: #0057FF; color: #0057FF;
        }

        /* Column Selector Drawer */
        .rajpsp-col-panel {
          background: #F8FAFC; border: 1px solid #CBD5E1; border-radius: 8px;
          padding: 8px 12px; margin-bottom: 8px; flex-shrink: 0;
          max-height: 96px; overflow-y: auto;
        }
        .rajpsp-col-panel-header {
          display: flex; align-items: center; justify-content: space-between;
          font-size: 12px; font-weight: 600; color: #0F172A; margin-bottom: 8px;
        }
        .rajpsp-col-panel-actions button {
          background: none; border: none; color: #0057FF; font-size: 11px;
          font-weight: 600; cursor: pointer; padding: 0 4px;
        }
        .rajpsp-col-pills-wrap {
          display: flex; flex-wrap: wrap; gap: 6px; max-height: 100px; overflow-y: auto;
        }
        .rajpsp-col-pill {
          display: inline-flex; align-items: center; gap: 5px; background: #FFFFFF;
          border: 1px solid #E2E8F0; padding: 3px 8px; border-radius: 14px;
          font-size: 11px; color: #475569; cursor: pointer; user-select: none;
          transition: all 0.15s;
        }
        .rajpsp-col-pill.active {
          background: #EFF6FF; border-color: #93C5FD; color: #1D4ED8; font-weight: 600;
        }

        /* Table & Scrolling */
        .rajpsp-preview-scroll {
          flex: 1 1 auto;
          min-height: 150px;
          max-height: calc(100vh - 210px);
          overflow-y: auto; overflow-x: auto;
          border: 1px solid #EBE8DE; border-radius: 8px;
          box-shadow: inset 0 1px 3px rgba(0,0,0,0.02);
        }
        .rajpsp-table {
          width: 100%; border-collapse: separate; border-spacing: 0;
          font-size: 12px; white-space: nowrap;
        }
        .rajpsp-table th {
          background: #F8F7F4; padding: 9px 12px; border-bottom: 2px solid #DCD8CB;
          text-align: left; font-weight: 700; color: #0F172A; position: sticky; top: 0; z-index: 5;
        }
        .rajpsp-table td {
          padding: 8px 12px; border-bottom: 1px solid #F1EFEA; color: #334155;
        }
        .rajpsp-table tbody tr { cursor: pointer; }
        .rajpsp-table tbody tr:hover td { background: #F8FAFC; }
        .rajpsp-table tbody tr.selected td { background: #EFF6FF; }
        .rajpsp-table input[type="checkbox"] { cursor: pointer; accent-color: #0057FF; }

        .rajpsp-preview-footer {
          display: flex; align-items: center; justify-content: space-between;
          flex-wrap: wrap; gap: 10px; margin-top: 10px; padding-top: 8px;
          border-top: 1px solid #EBE8DE; flex-shrink: 0;
        }
        .rajpsp-footer-tip { font-size: 11px; color: #64748B; }
      `;
      document.head.appendChild(style);
    }
  };

  window.RVSSAHWidget = RajPSPWidget;
  window.RVSSAH = RajPSPWidget;
  window.RajPSPWidget = RajPSPWidget;
})(window);
