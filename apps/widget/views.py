import time
from django.shortcuts import render
from django.views import View
from django.http import HttpResponse
from apps.accounts.models import APIKey


class WidgetDemoView(View):
    """Interactive testbed demonstrating the widget inside a simulated third-party school website."""
    def get(self, request):
        first_key = APIKey.objects.filter(is_active=True).first()
        demo_key_prefix = first_key.key_prefix if first_key else "demo_key"
        return render(request, 'widget_demo.html', {
            'demo_key_prefix': demo_key_prefix,
            'build_timestamp': int(time.time())
        })


class DeveloperDocsView(View):
    """Developer portal showcasing REST API endpoints, cURL examples, and widget embed code."""
    def get(self, request):
        first_key = APIKey.objects.filter(is_active=True).first()
        demo_key = first_key.key_prefix if first_key else "sk_live_demo_sample_key"
        return render(request, 'developer_docs.html', {
            'demo_key': demo_key,
            'build_timestamp': int(time.time())
        })


class LLMsTxtView(View):
    """Machine-readable developer documentation for AI models (Cursor, ChatGPT, Claude, Windsurf, v0, Bolt)."""
    def get(self, request):
        host = request.get_host()
        protocol = "https" if request.is_secure() else "http"
        base_url = f"{protocol}://{host}"

        content = f"""# RVS SAH - Student Add Helper API & Embeddable Widget

> Machine-readable integration specification for AI coding assistants (Cursor, ChatGPT, Claude, v0, Bolt.new, Lovable, Windsurf).
> RVS SAH provides pass-through, automated student data extraction from Rajasthan Private School Portal (rajpsp.rajasthan.gov.in) into client school ERPs and web applications.

## Integration Method 1: Drop-In Embeddable Widget (Client-Side)

Best for: Any web application (Vanilla HTML/JS, PHP, WordPress, Laravel, Django templates, React, Vue).

### 1. Include Script Tag
```html
<script src="{base_url}/static/widget/widget.js"></script>
```

### 2. Add Trigger Button
```html
<button id="import-students-btn" type="button">Import Students with RVS SAH</button>
```

### 3. Initialize SDK
```javascript
RVSSAHWidget.init({{
  apiKey: "sk_live_your_api_key_here",
  triggerElement: "#import-students-btn",
  mode: "modal", // "modal" (popup) or "inline" (embedded in container)
  container: "#my-inline-container", // required only if mode is "inline"
  onSuccess: function(data) {{
    // data payload structure:
    // data.success: true
    // data.school_code: "P25814"
    // data.school_name: "ABC School"
    // data.session: "2024-2025"
    // data.class_name: "First"
    // data.count: 68 (number of imported student rows)
    // data.total_extracted: 68
    // data.headers: ["S.No.", "NIC Student ID", "Student Name", "Father Name", ...]
    // data.students: [["1", "545411947", "ABHI KUMAR JOGI", "PREM SINGH", ...], ...]
    console.log("Successfully extracted students:", data.students);
    saveStudentsToERP(data.students);
  }},
  onError: function(error) {{
    console.error("RVS SAH Error:", error.message);
  }}
}});
```

---

## Integration Method 2: React / Next.js Component (TypeScript)

Best for: Next.js (App / Pages router), React, Vite, Tailwind CSS, v0.dev, Bolt.new, Lovable.

```tsx
import React, {{ useEffect }} from 'react';

declare global {{
  interface Window {{
    RVSSAHWidget: any;
  }}
}}

export interface RvsSahPayload {{
  success: boolean;
  school_code: string;
  school_name: string;
  session: string;
  class_name: string;
  count: number;
  total_extracted: number;
  headers: string[];
  students: string[][];
}}

interface RvsSahButtonProps {{
  apiKey: string;
  onSuccess: (data: RvsSahPayload) => void;
  onError?: (err: Error) => void;
  className?: string;
  buttonText?: string;
}}

export const RvsSahButton: React.FC<RvsSahButtonProps> = ({{
  apiKey,
  onSuccess,
  onError,
  className = "px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded-lg shadow transition",
  buttonText = "Import Students with RVS SAH"
}}) => {{
  useEffect(() => {{
    const scriptId = 'rvs-sah-sdk';
    if (!document.getElementById(scriptId)) {{
      const script = document.createElement('script');
      script.id = scriptId;
      script.src = '{base_url}/static/widget/widget.js';
      script.async = true;
      script.onload = () => bindWidget();
      document.body.appendChild(script);
    }} else {{
      bindWidget();
    }}

    function bindWidget() {{
      if (window.RVSSAHWidget) {{
        window.RVSSAHWidget.init({{
          apiKey: apiKey,
          triggerElement: '#rvs-sah-import-trigger',
          mode: 'modal',
          onSuccess: (data: RvsSahPayload) => onSuccess(data),
          onError: (err: any) => onError ? onError(err) : console.error(err)
        }});
      }}
    }}
  }}, [apiKey, onSuccess, onError]);

  return (
    <button id="rvs-sah-import-trigger" type="button" className={{className}}>
      {{buttonText}}
    </button>
  );
}};
```

---

## Integration Method 3: Headless Backend REST API

Base URL: `{base_url}/api/v1`
Authentication: Header `Authorization: Bearer sk_live_...` or `X-API-Key: sk_live_...`

### Endpoints
1. `GET /account/status`
   Returns active subscription tier, monthly request quota, and remaining credits.

2. `POST /session/start`
   Starts an isolated Chromium context.
   Response: `{{ "session_id": "...", "captcha_b64": "data:image/png;base64,..." }}`

3. `POST /session/refresh-captcha`
   Body: `{{ "session_id": "..." }}`
   Response: `{{ "captcha_b64": "data:image/png;base64,..." }}`

4. `POST /session/login`
   Body: `{{ "session_id": "...", "username": "...", "password": "...", "captcha": "..." }}`
   Response: `{{ "success": true, "school_name": "...", "sessions": [...], "classes": [...] }}`

5. `POST /session/fetch-students`
   Body: `{{ "session_id": "...", "school_code": "...", "session_val": "2024-2025", "class_val": "1" }}`
   Response: `{{ "success": true, "count": 68, "headers": [...], "rows": [...] }}`

6. `POST /session/close`
   Body: `{{ "session_id": "..." }}`
   Destroys browser session and releases memory.

---

## Data Privacy & Compliance
- **Zero-Retention Pass-Through Architecture**: Student personal data (names, Aadhaar, parents' information, contact details) is strictly streamed to the client response and NEVER stored on RVS SAH servers.
- Fully compliant with India Digital Personal Data Protection (DPDP) Act.
"""
        return HttpResponse(content.strip(), content_type="text/plain; charset=utf-8")
