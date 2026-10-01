import time
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()

    dialogs = []
    page.on("dialog", lambda d: (dialogs.append(d.message), d.accept()))

    page.goto("https://rajpsp.rajasthan.gov.in/home/schoollogin.aspx")
    print("Page loaded. URL:", page.url)

    # Let's inspect SHA512 function on the page
    has_sha = page.evaluate("typeof window.SHA512 === 'function'")
    print("Has SHA512 function:", has_sha)

    # Inject fields directly WITHOUT ANY DISPATCHEVENT('CHANGE')
    username = "12345"
    password = "MyRealPassword123"
    captcha = "99999"

    page.evaluate(f"""() => {{
        const u = '{username}';
        const p = '{password}';
        const c = '{captcha}';

        document.getElementById('txtUNameschool').value = u;
        document.getElementById('hdnUserIdschool').value = u;

        const rand = document.getElementById('hdnRandNu512').value;

        // Exactly what Sha512authschool_New does:
        document.getElementById('hdnDempps').value = SHA512(p);
        document.getElementById('hdnDemppsSha512').value = SHA512(p);

        const sha = SHA512(u.toLowerCase() + p);
        const hashs = SHA512(rand + sha);
        document.getElementById('txtUPswdschool').value = hashs;

        document.getElementById('txtschool_Captcha').value = c;
    }}""")

    print("Fields populated in DOM:")
    print("  txtUNameschool:", page.input_value("#txtUNameschool"))
    print("  hdnUserIdschool:", page.input_value("#hdnUserIdschool"))
    print("  txtUPswdschool:", page.input_value("#txtUPswdschool")[:20], "...")
    print("  txtschool_Captcha:", page.input_value("#txtschool_Captcha"))
    print("  hdnRandNu512:", page.input_value("#hdnRandNu512")[:20], "...")

    # Now click login
    print("Clicking #btnloginschool...")
    page.click("#btnloginschool")
    time.sleep(3)

    print("Dialogs intercepted:", dialogs)
    print("Final URL:", page.url)

    # Check for labels
    labels = page.query_selector_all("[id*='lbl'], [id*='Msg'], [id*='Error'], .text-danger, .alert")
    for l in labels:
        try:
            txt = l.inner_text().strip()
            if txt:
                print(f"Label [{l.get_attribute('id')}]: {txt.encode('ascii', 'ignore').decode()}")
        except Exception:
            pass

    browser.close()
