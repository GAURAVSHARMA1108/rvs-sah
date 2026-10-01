# RVS SAH - Student Add Helper & Profile Extractor

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![Django](https://img.shields.io/badge/django-5.0%2B-green.svg)](https://www.djangoproject.com/)
[![Playwright](https://img.shields.io/badge/playwright-1.40%2B-red.svg)](https://playwright.dev/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**RVS SAH** is an enterprise-grade automation engine, embeddable SDK, and SaaS platform designed for Rajasthan Private School Portal administrators and school ERP systems. It enables seamless authentication, automated session/class synchronization, bilingual table parsing, selective row extraction, deep profile scraping (Aadhaar, Jan Aadhaar, bank records, categories), and Signal Blue Excel (`.xlsx`) exports.

---

## 🌟 Key Architecture & Capabilities

RVS SAH is built to work in two primary operating models:

### 1. Standalone Desktop Application (Local Mode)
- **Engine**: PyWebView + Playwright Chromium.
- **Workflow**: Automated login watcher, DOM synchronization, live table inspector, selective row checkboxes, deep profile scraping, and branded Excel/TSV exports.
- **UI Design**: Signal Blue (`#0057FF`) and Porcelain (`#F8F7F4`) clean design system.

### 2. Multi-Tenant SaaS Backend & Embeddable SDK
- **Backend**: Django 5.0 + Django REST Framework with API Key authentication (`x-api-key`).
- **REST APIs**:
  - `/api/v1/auth/` (Session initialization, dynamic CAPTCHA extraction, credential validation)
  - `/api/v1/dropdowns/` (Portal DOM synchronization for Session & Class)
  - `/api/v1/students/` (GridView table parsing & deep profile sub-form extraction)
  - `/api/v1/export/` (Automated Excel `.xlsx` generation)
  - `/api/v1/session/status/` & `/api/v1/session/close/` (Chromium lifecycle management)
- **Embeddable Widget (`rvs-sah-widget.js`)**:
  - Embeddable in any web application via `<script src=".../static/widget/widget.js"></script>`.
  - Supports **Modal Mode** (floating launcher button + responsive modal dialog) and **Inline Container Mode** (`containerId`).
  - Viewport-bounded responsive modal with pinned header, sticky footer, and scrollable table preview.
  - Multi-column and row selection with master checkboxes.
  - Custom JavaScript events: `onSuccess`, `onError`, `onCancel`.
- **AI-First Integration (`/llms.txt` & `/llms-full.txt`)**:
  - Machine-readable context endpoints formatted specifically for AI coding assistants (ChatGPT, Claude, Cursor, Copilot).
  - 1-Click "Copy Prompt for AI" in Developer Documentation.
  - Multi-framework code snippets (Vanilla JS, React/Next.js, Vue 3/Nuxt, Python, Node.js).

---

## 📁 Repository Structure

```
.
├── apps/
│   ├── accounts/          # Organization accounts & API key management
│   ├── billing/           # Subscription tiers & usage quota tracking
│   ├── scraper_api/       # DRF REST API endpoints & Chromium session manager
│   └── widget/            # Embeddable SDK & developer documentation views
├── saas_core/             # Django project settings, URLs, middleware & WSGI/ASGI
├── templates/
│   ├── widget_demo.html   # Interactive test harness & live SDK playground
│   └── developer_docs.html# Developer documentation & AI prompt integration
├── web/                   # Standalone desktop UI (HTML, CSS, JS)
├── app.py                 # Standalone desktop launcher (PyWebView)
├── browser_manager.py     # Playwright automation engine & portal DOM parser
├── exporter.py            # Excel (.xlsx) generator & TSV clipboard formatter
├── manage.py              # Django management script
├── requirements.txt       # Project dependencies
├── run.bat / run.ps1      # Quick launchers for Desktop App
├── run_saas.bat / run_saas.ps1 # Quick launchers for SaaS Server
└── README.md              # Project documentation
```

---

## 🚀 Quick Start Guide

### Prerequisites
- Python 3.10+ installed
- Chromium browser binaries (installed automatically via Playwright)

### 1. Installation
Clone the repository and install dependencies:
```bash
git clone https://github.com/GAURAVSHARMA1108/rvs-sah.git
cd rvs-sah

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# Linux/macOS:
source .venv/bin/activate

# Install requirements
pip install -r requirements.txt

# Install Playwright browser dependencies
playwright install chromium
```

---

### 2. Running the SaaS Server (API & Widget SDK)

1. **Apply Migrations**:
   ```bash
   python manage.py migrate
   ```

2. **Create Superuser (Optional)**:
   ```bash
   python manage.py createsuperuser
   ```

3. **Start the Django Development Server**:
   ```bash
   # Using script:
   .\run_saas.ps1
   # Or directly:
   python manage.py runserver 0.0.0.0:8085
   ```

4. **Access the Web Interfaces**:
   - **Interactive Widget Playground**: [http://localhost:8085/demo/](http://localhost:8085/demo/)
   - **Developer Docs & AI Integration**: [http://localhost:8085/docs/](http://localhost:8085/docs/)
   - **Machine-Readable AI Context**: [http://localhost:8085/llms.txt](http://localhost:8085/llms.txt)
   - **Django Admin Portal**: [http://localhost:8085/admin/](http://localhost:8085/admin/)

---

### 3. Running the Standalone Desktop Application

Double-click `run.bat` or run:
```powershell
.\run.ps1
```
Or execute directly:
```bash
python app.py
```

---

## 💻 Embeddable SDK Usage

### Method A: CDN / Script Tag
```html
<!-- Include SDK -->
<script src="http://localhost:8085/static/widget/widget.js"></script>

<script>
  RVSSAHWidget.init({
    apiKey: "YOUR_ORGANIZATION_API_KEY",
    baseUrl: "http://localhost:8085",
    theme: {
      primaryColor: "#0057FF",
      borderRadius: "12px"
    },
    onSuccess: function(data) {
      console.log("Students extracted:", data.students);
    },
    onError: function(err) {
      console.error("Widget error:", err);
    }
  });
</script>
```

### Method B: React / Next.js
```tsx
import { useEffect } from 'react';

declare global {
  interface Window {
    RVSSAHWidget: any;
  }
}

export default function StudentExtractor() {
  useEffect(() => {
    const script = document.createElement('script');
    script.src = 'http://localhost:8085/static/widget/widget.js';
    script.async = true;
    script.onload = () => {
      window.RVSSAHWidget?.init({
        apiKey: process.env.NEXT_PUBLIC_RVS_SAH_KEY,
        baseUrl: 'http://localhost:8085',
        onSuccess: (res: any) => console.log('Extracted:', res),
      });
    };
    document.body.appendChild(script);
  }, []);

  return <button onClick={() => window.RVSSAHWidget?.open()}>Open RVS SAH Extractor</button>;
}
```

---

## 🤖 AI-First Integration
Developers building apps with AI assistants can use our curated prompts and direct `/llms.txt` endpoints:
- **LLMs.txt**: `http://localhost:8085/llms.txt`
- **Full API Specification**: `http://localhost:8085/llms-full.txt`
- **Copy AI Prompt**: Visit the [Developer Docs](http://localhost:8085/docs/) and click **"Copy Prompt for AI"** to immediately instruct Cursor, Claude, or Copilot to integrate RVS SAH.

---

## 📄 License
This project is licensed under the MIT License - see the LICENSE file for details.
