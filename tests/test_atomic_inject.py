from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()

    dialog_messages = []
    def on_dlg(dialog):
        print(f"PORTAL ALERT DIALOG: '{dialog.message}'")
        dialog_messages.append(dialog.message)
        dialog.accept()

    page.on("dialog", on_dlg)

    page.goto("https://rajpsp.rajasthan.gov.in/home/schoollogin.aspx")

    username = "TEST_SCHOOL_CODE"
    password = "MyPassword123"
    captcha = "12345"

    # Inject all fields cleanly and compute SHA512 in one atomic JS execution
    injection_res = page.evaluate("""
    (args) => {
        const u = args.username;
        const p = args.password;
        const c = args.captcha;

        // Set inputs
        const uInput = document.getElementById('txtUNameschool');
        const hdnUser = document.getElementById('hdnUserIdschool');
        const pInput = document.getElementById('txtUPswdschool');
        const cInput = document.getElementById('txtschool_Captcha');
        const randInput = document.getElementById('hdnRandNu512');
        const dempps = document.getElementById('hdnDempps');
        const demppsSha = document.getElementById('hdnDemppsSha512');

        if (!uInput || !pInput || !cInput) {
            return { success: false, reason: "Login input fields not found in DOM." };
        }

        uInput.value = u;
        if (hdnUser) hdnUser.value = u;

        const rand = randInput ? randInput.value : '';

        // Compute exact portal SHA512
        if (typeof SHA512 === 'function') {
            if (dempps) dempps.value = SHA512(p);
            if (demppsSha) demppsSha.value = SHA512(p);
            const sha = SHA512(u.toLowerCase() + p);
            const hashs = SHA512(rand + sha);
            pInput.value = hashs;
        } else {
            pInput.value = p;
        }

        cInput.value = c;

        // Verify validators
        let isValid = true;
        if (typeof Page_ClientValidate === 'function') {
            isValid = Page_ClientValidate('val');
        }

        return {
            success: true,
            isValid: isValid,
            uVal: uInput.value,
            pLength: pInput.value.length,
            cVal: cInput.value
        };
    }
    """, {"username": username, "password": password, "captcha": captcha})

    print("Injection result:", injection_res)

    # Click login button
    print("Clicking #btnloginschool...")
    page.click("#btnloginschool")

    # Wait for either navigation or alert dialog
    for _ in range(12):
        if dialog_messages or "schoollogin" not in page.url.lower():
            break
        time.sleep(0.5)

    print("Captured dialogs:", dialog_messages)
    print("Final URL:", page.url)

    browser.close()
