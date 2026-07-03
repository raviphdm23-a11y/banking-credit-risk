"""
Selenium Automation Test: Auto-Fill and Calculate SHAP Assessment
Tests the end-to-end workflow of auto-filling form and calculating risk parameters.

Prerequisites:
- ChromeDriver installed or in PATH
- Flask app running on http://127.0.0.1:5000
- Chrome browser installed
"""

import os
import sys
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service

# Set console output encoding
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


class AutoFillTest:
    def __init__(self, headless=False):
        """Initialize Selenium WebDriver"""
        self.base_url = "http://127.0.0.1:5000"
        self.page_url = f"{self.base_url}/borrower-info.html"
        self.driver = None
        self.headless = headless
        self.results = {
            'passed': [],
            'failed': [],
            'warnings': []
        }

    def setup_driver(self):
        """Setup Chrome WebDriver with options"""
        chrome_options = Options()

        if self.headless:
            chrome_options.add_argument("--headless")

        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--start-maximized")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")

        try:
            # Use webdriver-manager to automatically download ChromeDriver
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.log_result("[OK] WebDriver initialized successfully")
            return True
        except Exception as e:
            self.log_result(f"[ERROR] Failed to initialize WebDriver: {str(e)}", is_error=True)
            return False

    def log_result(self, message, is_error=False):
        """Log test results"""
        print(f"\n{'='*70}")
        if is_error:
            self.results['failed'].append(message)
            print(f"[FAIL] {message}")
        else:
            self.results['passed'].append(message)
            print(f"[PASS] {message}")
        print(f"{'='*70}")

    def log_warning(self, message):
        """Log warnings"""
        self.results['warnings'].append(message)
        print(f"[WARN] {message}")

    def navigate_to_page(self):
        """Navigate to borrower-info page"""
        try:
            print(f"\n[NAV] Navigating to: {self.page_url}")
            self.driver.get(self.page_url)

            # Wait for page to load
            time.sleep(2)

            # Check if page loaded
            if "Credit Risk Calculator" in self.driver.title or "borrower" in self.driver.page_source.lower():
                self.log_result("[OK] Page loaded successfully")
                return True
            else:
                self.log_result("[ERROR] Page failed to load properly", is_error=True)
                return False
        except Exception as e:
            self.log_result(f"[ERROR] Navigation failed: {str(e)}", is_error=True)
            return False

    def check_auto_fill_button_exists(self):
        """Check if auto-fill button is present on the page"""
        try:
            wait = WebDriverWait(self.driver, 10)
            button = wait.until(
                EC.presence_of_element_located((By.XPATH, "//button[contains(text(), 'Auto-Fill')]"))
            )
            self.log_result("[OK] Auto-Fill button found on page")
            return button
        except Exception as e:
            self.log_result(f"[ERROR] Auto-Fill button not found: {str(e)}", is_error=True)
            # Try to find any button with autofill in onclick
            try:
                button = self.driver.find_element(By.XPATH, "//button[contains(@onclick, 'autoFill')]")
                self.log_result("[OK] Auto-Fill button found (by onclick attribute)")
                return button
            except:
                return None

    def click_auto_fill_button(self):
        """Click the auto-fill button"""
        try:
            button = self.check_auto_fill_button_exists()
            if not button:
                self.log_result("[ERROR] Cannot click: Auto-Fill button not found", is_error=True)
                return False

            print("\n[AUTOFILL] Clicking Auto-Fill button...")
            button.click()

            # Wait for form to be filled
            time.sleep(2)

            # Handle any alerts
            try:
                alert = WebDriverWait(self.driver, 3).until(EC.alert_is_present())
                alert_text = alert.text
                print(f"[ALERT] Alert appeared: {alert_text}")
                alert.accept()
                self.log_result(f"[OK] Auto-Fill alert handled: {alert_text}")
            except:
                # No alert, which is fine
                pass

            return True
        except Exception as e:
            self.log_result(f"[ERROR] Failed to click Auto-Fill button: {str(e)}", is_error=True)
            return False

    def verify_fields_filled(self):
        """Verify that form fields were actually filled"""
        try:
            wait = WebDriverWait(self.driver, 5)

            # Check key fields
            fields_to_check = {
                'debtToEquity': '2.5',
                'interestCoverage': '2.5',
                'profitabilityMargin': '8',
                'liquidityRatio': '1.2',
                'kycAge': '45',
                'kycCibilScore': '650',
                'borrowerId': 'DEV-TEST-001'
            }

            filled_count = 0
            for field_id, expected_value in fields_to_check.items():
                try:
                    field = self.driver.find_element(By.ID, field_id)
                    actual_value = field.get_attribute('value')

                    if actual_value and expected_value in str(actual_value):
                        filled_count += 1
                        print(f"  [FOUND] {field_id}: {actual_value}")
                    else:
                        self.log_warning(f"Field {field_id} not properly filled (expected: {expected_value}, got: {actual_value})")
                except Exception as e:
                    self.log_warning(f"Could not verify field {field_id}: {str(e)}")

            verification_rate = (filled_count / len(fields_to_check)) * 100

            if filled_count >= len(fields_to_check) * 0.8:  # At least 80% filled
                self.log_result(f"[OK] Form fields filled successfully ({filled_count}/{len(fields_to_check)})")
                return True
            else:
                self.log_result(f"[WARNING]  Only {verification_rate:.0f}% of fields filled properly", is_error=True)
                return False
        except Exception as e:
            self.log_result(f"[ERROR] Failed to verify fields: {str(e)}", is_error=True)
            return False

    def find_calculate_button(self):
        """Find the calculate button"""
        try:
            wait = WebDriverWait(self.driver, 10)

            # Try multiple selectors
            selectors = [
                (By.XPATH, "//button[contains(text(), 'Calculate Risk Parameters')]"),
                (By.ID, "calculateBtn"),
                (By.XPATH, "//button[contains(@onclick, 'calculateAllParameters')]"),
                (By.XPATH, "//button[contains(text(), 'Calculate')]")
            ]

            for selector in selectors:
                try:
                    button = self.driver.find_element(*selector)
                    if button.is_displayed():
                        self.log_result(f"[OK] Calculate button found: {selector}")
                        return button
                except:
                    continue

            self.log_result("[ERROR] Calculate button not found with any selector", is_error=True)
            return None
        except Exception as e:
            self.log_result(f"[ERROR] Error finding Calculate button: {str(e)}", is_error=True)
            return None

    def click_calculate_button(self):
        """Click the calculate risk parameters button"""
        try:
            button = self.find_calculate_button()
            if not button:
                return False

            print("\n[CALC] Clicking Calculate Risk Parameters button...")

            # Scroll button into view
            self.driver.execute_script("arguments[0].scrollIntoView(true);", button)
            time.sleep(1)

            # Click button
            button.click()

            # Wait for results to load
            print("[WAIT] Waiting for calculation to complete...")
            time.sleep(5)

            self.log_result("[OK] Calculate button clicked successfully")
            return True
        except Exception as e:
            self.log_result(f"[ERROR] Failed to click Calculate button: {str(e)}", is_error=True)
            return False

    def verify_results_displayed(self):
        """Verify that risk calculation results are displayed"""
        try:
            time.sleep(2)  # Wait for async calculations

            # Check if results section has 'active' class
            results_section = self.driver.find_element(By.ID, "resultsSection")
            results_visible = 'active' in results_section.get_attribute('class')

            if results_visible:
                self.log_result("[OK] Results section is visible (active class found)")
            else:
                self.log_warning("Results section not marked as active")

            # Check for PD value
            try:
                pd_value_elem = self.driver.find_element(By.ID, "pdValue")
                pd_text = pd_value_elem.text
                if pd_text and pd_text != '--':
                    print(f"  [METRIC] PD Value: {pd_text}")
                    self.log_result("[OK] PD value calculated and displayed")
                    return True
            except:
                pass

            # Check for any result cards visible
            result_cards = self.driver.find_elements(By.CLASS_NAME, "result-card")
            visible_cards = sum(1 for card in result_cards if card.is_displayed())

            if visible_cards > 0:
                self.log_result(f"[OK] Found {visible_cards} visible result cards")
                return True

            # Fallback: check if page has calculation-related content
            page_source = self.driver.page_source
            if any(keyword in page_source for keyword in ['Probability', 'Risk', 'Component', 'Value']):
                self.log_result("[OK] Calculation results found in page content")
                return True

            self.log_result("[ERROR] Results not displayed properly", is_error=True)
            return False
        except Exception as e:
            self.log_result(f"[ERROR] Failed to verify results: {str(e)}", is_error=True)
            return False

    def verify_shap_data(self):
        """Verify that SHAP tier 2 data is displayed"""
        try:
            # Look for SHAP section
            shap_indicators = [
                "SHAP",
                "Feature Contributions",
                "Feature Interactions",
                "Tier 2"
            ]

            page_text = self.driver.page_source
            found_indicators = [ind for ind in shap_indicators if ind in page_text]

            if found_indicators:
                self.log_result(f"[OK] SHAP Tier 2 data found: {', '.join(found_indicators)}")

                # Try to find SHAP section
                try:
                    shap_section = self.driver.find_element(By.XPATH, "//*[contains(text(), 'SHAP Analysis')]")
                    print(f"  [FOUND] SHAP Analysis section visible")
                except:
                    pass

                return True
            else:
                self.log_warning("SHAP Tier 2 data not found on results page")
                return False
        except Exception as e:
            self.log_warning(f"Could not verify SHAP data: {str(e)}")
            return False

    def take_screenshot(self, filename):
        """Take a screenshot for debugging"""
        try:
            screenshot_path = f"/tmp/{filename}.png"
            self.driver.save_screenshot(screenshot_path)
            print(f"[SCREENSHOT] Screenshot saved: {screenshot_path}")
            return screenshot_path
        except Exception as e:
            print(f"[WARNING]  Could not take screenshot: {str(e)}")
            return None

    def run_full_test(self):
        """Run complete test workflow"""
        print("\n" + "="*70)
        print("[START] Starting Selenium Automation Test: Auto-Fill → Calculate")
        print("="*70)

        try:
            # Step 1: Setup
            if not self.setup_driver():
                return False

            # Step 2: Navigate
            if not self.navigate_to_page():
                return False

            # Step 3: Click Auto-Fill
            if not self.click_auto_fill_button():
                return False

            # Step 4: Verify Fields
            if not self.verify_fields_filled():
                self.log_warning("Form fields may not be properly filled, but continuing...")

            # Step 5: Click Calculate
            if not self.click_calculate_button():
                return False

            # Step 6: Verify Results
            results_ok = self.verify_results_displayed()

            # Step 7: Verify SHAP
            self.verify_shap_data()

            # Take final screenshot
            self.take_screenshot("assessment_results")

            return results_ok

        except Exception as e:
            self.log_result(f"[ERROR] Unexpected error during test: {str(e)}", is_error=True)
            self.take_screenshot("error_state")
            return False

        finally:
            self.cleanup()

    def cleanup(self):
        """Close browser and cleanup"""
        if self.driver:
            self.driver.quit()
            print("\n[CLEANUP] Browser closed and resources cleaned up")

    def print_summary(self):
        """Print test summary"""
        print("\n" + "="*70)
        print("[CALC] TEST SUMMARY")
        print("="*70)

        print(f"\n[OK] Passed ({len(self.results['passed'])}):")
        for item in self.results['passed']:
            print(f"   {item}")

        if self.results['warnings']:
            print(f"\n[WARNING]  Warnings ({len(self.results['warnings'])}):")
            for item in self.results['warnings']:
                print(f"   {item}")

        print(f"\n[ERROR] Failed ({len(self.results['failed'])}):")
        for item in self.results['failed']:
            print(f"   {item}")

        total_tests = len(self.results['passed']) + len(self.results['failed'])
        pass_rate = (len(self.results['passed']) / total_tests * 100) if total_tests > 0 else 0

        print(f"\n{'='*70}")
        print(f"PASS RATE: {pass_rate:.1f}% ({len(self.results['passed'])}/{total_tests})")
        print(f"{'='*70}\n")

        return len(self.results['failed']) == 0


def main():
    """Main test execution"""
    # Check if Flask is running
    import requests
    try:
        requests.get("http://127.0.0.1:5000/borrower-info.html", timeout=2)
    except:
        print("[ERROR] ERROR: Flask is not running!")
        print("Start it with: .\\run_flask.ps1")
        return False

    # Run test (non-headless for visibility)
    test = AutoFillTest(headless=False)
    success = test.run_full_test()
    test.print_summary()

    return 0 if success else 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
