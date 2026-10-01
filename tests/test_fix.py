from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()

    dialog_message = []
    def on_dlg(dialog):
        print(f">>> WEBSITE DIALOG RECEIVED: '{dialog.message}' (type={dialog.type})")
        dialog_message.append(dialog.message)
        try:
            dialog.accept()
        except Exception:
            pass

    page.on("dialog", on_dlg)

    page.goto("https://rajpsp.rajasthan.gov.in/home/schoollogin.aspx")

    username = "12345"
    password = "MyPassword123"
    captcha = "99999"

    print("Step 1: Setting hdnUserIdschool and txtUNameschool...")
    page.evaluate(f"""() => {{
        document.getElementById('hdnUserIdschool').value = '{username}';
        document.getElementById('txtUNameschool').value = '{username}';
    }}""")

    print("Step 2: Filling txtUPswdschool and running blur...")
    page.click("#txtUPswdschool")
    page.keyboard.type(password)
    page.keyboard.press("Tab")

    time.sleep(0.5)
    print("Password value after blur (hashed):", page.input_value("#txtUPswdschool")[:20], "...")

    print("Step 3: Filling captcha...")
    page.click("#txtschool_Captcha")
    page.keyboard.type(captcha)

    print("Step 4: Clicking #btnloginschool...")
    page.click("#btnloginschool")

    # Wait for response / dialog
    for _ in range(10):
        if dialog_message:
            break
        time.sleep(0.5)

    print("--- RESULT SUMMARY ---")
    print("Dialogs captured from website:", dialog_message)
    print("Final URL:", page.url)

    time.sleep(1)
    browser.close()
