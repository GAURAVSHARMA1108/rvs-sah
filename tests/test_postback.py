import time, hashlib
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto("https://rajpsp.rajasthan.gov.in/home/schoollogin.aspx")

    img1 = page.query_selector("#captchimg").screenshot()
    h1 = hashlib.md5(img1).hexdigest()
    print("Initial Captcha MD5:", h1)

    # Enter username and fire change
    page.fill("#txtUNameschool", "12345")
    page.evaluate("() => document.getElementById('txtUNameschool').dispatchEvent(new Event('change', { bubbles: true }))")

    time.sleep(3)

    img2 = page.query_selector("#captchimg").screenshot()
    h2 = hashlib.md5(img2).hexdigest()
    print("Captcha MD5 after change event:", h2)
    print("Did Captcha change?:", h1 != h2)

    print("txtUNameschool after change:", page.input_value("#txtUNameschool"))
    print("hdnUserIdschool after change:", page.input_value("#hdnUserIdschool"))

    browser.close()
