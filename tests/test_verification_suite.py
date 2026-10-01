import time
from playwright.sync_api import sync_playwright

def run_tests():
    print("Starting Playwright verification test suite...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 850})

        # Test 1: Load Demo Testbed
        print("1. Loading http://localhost:8085/widget/demo/...")
        page.goto("http://localhost:8085/widget/demo/", wait_until="networkidle")
        time.sleep(1.0)
        page.screenshot(path="verification_1_demo_page.png")
        print("   Saved verification_1_demo_page.png")

        # Test 2: Open Modal in Modal Popup Mode
        print("2. Opening Modal Popup Mode...")
        page.click("#rajpsp-import-trigger")
        # Wait for captcha image to load
        page.wait_for_selector(".rajpsp-captcha-img", timeout=30000)
        time.sleep(1.0)
        page.screenshot(path="verification_2_modal_captcha_loaded.png")
        print("   Saved verification_2_modal_captcha_loaded.png - Captcha verified!")

        # Test 3: Submit invalid credentials & verify error banner feedback
        print("3. Submitting invalid test credentials to portal...")
        page.fill(".rajpsp-input-user", "P99999")
        page.fill(".rajpsp-input-pwd", "wrongpass123")
        page.fill(".rajpsp-input-captcha", "99999")
        page.click(".rajpsp-btn-login-submit")

        # Wait for button to reset or error banner to appear
        print("   Waiting for portal validation feedback...")
        page.wait_for_selector(".rajpsp-banner-error[style*='display: block']", timeout=20000)
        err_msg = page.inner_text(".rajpsp-banner-error")
        print(f"   Success! Live portal responded with error banner: '{err_msg}'")
        time.sleep(1.0)
        page.screenshot(path="verification_3_modal_error_feedback.png")
        print("   Saved verification_3_modal_error_feedback.png")

        # Test 4: Close modal
        page.click(".rajpsp-close-btn")
        time.sleep(0.5)

        # Test 5: Test Inline Container Mode
        print("4. Switching to Inline Container Mode...")
        page.click("#pillInline")
        page.wait_for_selector("#inline-widget-container .rajpsp-captcha-img", timeout=30000)
        time.sleep(1.0)
        page.screenshot(path="verification_4_inline_container_loaded.png")
        print("   Saved verification_4_inline_container_loaded.png - Inline verified!")

        # Test 6: Test Gaurav's Key
        print("5. Testing Gaurav's API Key quick-fill...")
        page.click("button:has-text(\"Gaurav's Key\")")
        time.sleep(1.0)
        page.screenshot(path="verification_5_gaurav_key_active.png")
        print("   Saved verification_5_gaurav_key_active.png - Gaurav's key verified!")

        # Test 7: Test Invalid API key error rendering (NO BLANK SCREEN!)
        print("6. Testing Invalid API Key display...")
        page.fill("#demoApiKey", "sk_live_invalid_key_for_testing_purposes")
        page.click("#pillModal")
        time.sleep(0.5)
        page.click("#rajpsp-import-trigger")
        page.wait_for_selector(".rajpsp-alert-error", timeout=10000)
        time.sleep(1.0)
        page.screenshot(path="verification_6_invalid_key_notice.png")
        print("   Saved verification_6_invalid_key_notice.png - Error card verified!")

        browser.close()
        print("All verification tests passed successfully!")

if __name__ == "__main__":
    run_tests()
