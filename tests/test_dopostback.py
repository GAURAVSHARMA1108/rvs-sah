import time
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()

    page.goto("https://rajpsp.rajasthan.gov.in/home/schoollogin.aspx")

    # Call __doPostBack via window.eval (which runs in non-strict mode)
    print("Calling __doPostBack via window.eval...")
    page.evaluate("""() => {
        window.eval("document.getElementById('txtUNameschool').value = '12345'; setTimeout(\\"__doPostBack('txtUNameschool','')\\", 0);");
    }""")

    time.sleep(3)

    print("txtUNameschool:", page.input_value("#txtUNameschool"))
    print("hdnUserIdschool:", page.input_value("#hdnUserIdschool"))
    print("hdnRandNu512:", page.input_value("#hdnRandNu512")[:30])

    browser.close()
