import time
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()

    dialogs = []
    page.on("dialog", lambda d: (dialogs.append(d.message), d.accept()))

    page.goto("https://rajpsp.rajasthan.gov.in/home/schoollogin.aspx")

    # Simulate exactly how a human types into the form
    print("Typing username...")
    page.click("#txtUNameschool")
    page.keyboard.type("12345")

    print("Typing password...")
    page.click("#txtUPswdschool")
    page.keyboard.type("MyPassword123")

    print("Typing captcha...")
    page.click("#txtschool_Captcha")
    page.keyboard.type("54321")

    print("State before click:")
    print("  txtUNameschool:", page.input_value("#txtUNameschool"))
    print("  txtUPswdschool:", page.input_value("#txtUPswdschool"))
    print("  hdnUserIdschool:", page.input_value("#hdnUserIdschool"))
    print("  hdnRandNu512:", page.input_value("#hdnRandNu512")[:20])

    print("Clicking login button...")
    page.click("#btnloginschool")
    time.sleep(3)

    print("Dialogs:", dialogs)
    print("URL after click:", page.url)

    browser.close()
