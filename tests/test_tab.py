import time
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()

    def on_resp(resp):
        if "schoollogin" in resp.url:
            print("Response:", resp.url, resp.status)
    page.on("response", on_resp)

    page.goto("https://rajpsp.rajasthan.gov.in/home/schoollogin.aspx")
    print("Initial hdnUserIdschool:", page.input_value("#hdnUserIdschool"))
    print("Initial hdnRandNu512:", page.input_value("#hdnRandNu512")[:20])

    # Click on txtUNameschool, type '12345', then press Tab
    page.click("#txtUNameschool")
    page.keyboard.type("12345")
    page.keyboard.press("Tab")

    time.sleep(3)

    print("After Tab:")
    print("  txtUNameschool:", page.input_value("#txtUNameschool"))
    print("  hdnUserIdschool:", page.input_value("#hdnUserIdschool"))
    print("  hdnRandNu512:", page.input_value("#hdnRandNu512")[:20])

    browser.close()
