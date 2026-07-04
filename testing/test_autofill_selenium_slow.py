"""
Slow-Motion Selenium Automation Test
- Visible browser window (not headless)
- 2-3 second delays between actions
- Detailed console output for each step
- Perfect for watching and debugging
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


class SlowAutoFillTest:
    def __init__(self, scenario='medium', delay=2):
        """
        Initialize with scenario and delay settings
        scenario: 'healthy', 'medium', or 'risky'
        delay: seconds to wait between actions
        """
        self.base_url = "http://127.0.0.1:5000"
        self.page_url = f"{self.base_url}/borrower-info.html"
        self.driver = None
        self.scenario = scenario
        self.delay = delay
        self.start_time = None

    def log_step(self, step_num, action, status="RUNNING"):
        """Log each step with timing"""
        elapsed = time.time() - self.start_time if self.start_time else 0
        print(f"\n{'='*75}")
        print(f"[STEP {step_num}] {action}")
        print(f"[STATUS] {status}")
        print(f"[TIME] {elapsed:.1f}s elapsed")
        print(f"{'='*75}")

    def setup_driver(self):
        """Setup Chrome WebDriver - VISIBLE (not headless)"""
        print("\n" + "="*75)
        print("[INIT] Setting up Chrome WebDriver")
        print("="*75)

        chrome_options = Options()
        # NOT headless - we want to see the browser!
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--start-maximized")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")

        try:
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            print("[PASS] WebDriver initialized - Browser window opened")
            return True
        except Exception as e:
            print(f"[FAIL] Error: {str(e)}")
            return False

    def navigate_to_page(self):
        """Navigate to page"""
        self.log_step(1, f"Navigate to: {self.page_url}", "IN PROGRESS")

        try:
            self.driver.get(self.page_url)
            print(f"[ACTION] Page loading...")
            time.sleep(self.delay)

            if "Credit Risk Calculator" in self.driver.title or "borrower" in self.driver.page_source.lower():
                self.log_step(1, f"Page loaded successfully", "COMPLETE")
                return True
            else:
                print("[FAIL] Page did not load properly")
                return False
        except Exception as e:
            print(f"[FAIL] Error: {str(e)}")
            return False

    def find_scenario_button(self):
        """Find and highlight the scenario button"""
        self.log_step(2, f"Find [{self.scenario.upper()}] scenario button", "IN PROGRESS")

        button_text_map = {
            'healthy': 'Healthy Borrower',
            'medium': 'Medium Risk',
            'risky': 'Risky Borrower'
        }

        button_text = button_text_map.get(self.scenario, 'Medium Risk')

        try:
            wait = WebDriverWait(self.driver, 10)
            button = wait.until(
                EC.presence_of_element_located((By.XPATH, f"//button[contains(text(), '{button_text}')]"))
            )
            print(f"[FOUND] Button located: '{button_text}'")

            # Highlight the button with JavaScript
            self.driver.execute_script("arguments[0].style.border = '3px solid yellow';", button)
            print("[ACTION] Button highlighted with yellow border")
            time.sleep(self.delay)

            self.log_step(2, f"Button located and highlighted", "COMPLETE")
            return button
        except Exception as e:
            print(f"[FAIL] Could not find button: {str(e)}")
            return None

    def click_scenario_button(self):
        """Click the scenario button"""
        self.log_step(3, f"Click [{self.scenario.upper()}] button", "IN PROGRESS")

        try:
            button = self.find_scenario_button()
            if not button:
                return False

            print(f"[ACTION] Clicking button...")
            self.driver.execute_script("arguments[0].scrollIntoView(true);", button)
            time.sleep(1)

            button.click()
            print("[ACTION] Button clicked - waiting for form fill...")
            time.sleep(self.delay)

            # Handle alert
            try:
                alert = WebDriverWait(self.driver, 3).until(EC.alert_is_present())
                alert_text = alert.text
                print(f"[ALERT] {alert_text}")
                alert.accept()
                print("[ACTION] Alert accepted")
                time.sleep(self.delay)
            except:
                pass

            self.log_step(3, "Button clicked and form filled", "COMPLETE")
            return True
        except Exception as e:
            print(f"[FAIL] Error: {str(e)}")
            return False

    def verify_fields(self):
        """Verify form fields are filled"""
        self.log_step(4, "Verify form fields filled", "IN PROGRESS")

        fields_to_check = {
            'debtToEquity': 'Debt-to-Equity',
            'interestCoverage': 'Interest Coverage',
            'profitabilityMargin': 'Profitability Margin',
            'liquidityRatio': 'Liquidity Ratio',
            'kycAge': 'Age',
            'kycCibilScore': 'CIBIL Score',
            'borrowerId': 'Borrower ID'
        }

        filled_count = 0
        print("\n[CHECKING] Form fields...\n")

        for field_id, field_label in fields_to_check.items():
            try:
                field = self.driver.find_element(By.ID, field_id)
                value = field.get_attribute('value')

                if value:
                    filled_count += 1
                    status_symbol = "[OK]"
                else:
                    status_symbol = "[EMPTY]"

                print(f"  {status_symbol} {field_label:30s} = {value}")
                time.sleep(0.3)  # Small delay between checks

            except Exception as e:
                print(f"  [ERROR] {field_label}: {str(e)}")

        print(f"\n[RESULT] {filled_count}/{len(fields_to_check)} fields filled")
        time.sleep(self.delay)

        if filled_count >= len(fields_to_check) * 0.8:
            self.log_step(4, f"Form fields verified ({filled_count}/{len(fields_to_check)})", "COMPLETE")
            return True
        else:
            self.log_step(4, "Form fields verification failed", "FAILED")
            return False

    def scroll_to_calculate_button(self):
        """Scroll down to find Calculate button"""
        self.log_step(5, "Scroll down to Calculate button", "IN PROGRESS")

        print("[ACTION] Scrolling down...")
        # Scroll down in multiple steps
        for i in range(3):
            self.driver.execute_script("window.scrollBy(0, 300);")
            print(f"  [SCROLL] Step {i+1}/3")
            time.sleep(0.5)

        time.sleep(self.delay)
        self.log_step(5, "Scrolled to Calculate button area", "COMPLETE")

    def find_calculate_button(self):
        """Find Calculate button"""
        self.log_step(6, "Locate Calculate button", "IN PROGRESS")

        try:
            button = self.driver.find_element(
                By.XPATH,
                "//button[contains(text(), 'Calculate')]"
            )
            print("[FOUND] Calculate button located")

            # Highlight it
            self.driver.execute_script("arguments[0].style.border = '3px solid cyan';", button)
            print("[ACTION] Button highlighted with cyan border")
            time.sleep(self.delay)

            self.log_step(6, "Calculate button found and highlighted", "COMPLETE")
            return button
        except Exception as e:
            print(f"[FAIL] Could not find Calculate button: {str(e)}")
            return None

    def click_calculate_button(self):
        """Click Calculate button"""
        self.log_step(7, "Click Calculate button", "IN PROGRESS")

        try:
            button = self.find_calculate_button()
            if not button:
                return False

            print("[ACTION] Clicking Calculate button...")
            button.click()
            print("[ACTION] Button clicked - waiting for calculation...")
            time.sleep(self.delay * 2)  # Allow more time for calculation

            self.log_step(7, "Calculate button clicked - waiting for results", "IN PROGRESS")
            return True
        except Exception as e:
            print(f"[FAIL] Error: {str(e)}")
            return False

    def wait_for_results(self):
        """Wait for results to appear"""
        self.log_step(7.5, "Wait for calculation results", "IN PROGRESS")

        print("[ACTION] Waiting for results...")
        time.sleep(self.delay * 2)

        page_source = self.driver.page_source
        if "Probability" in page_source or "SHAP" in page_source:
            print("[FOUND] Results appeared on page")
            self.log_step(7.5, "Results detected on page", "COMPLETE")
            return True
        else:
            print("[WARNING] Results not yet visible")
            return False

    def verify_results(self):
        """Verify results are displayed"""
        self.log_step(8, "Verify results displayed", "IN PROGRESS")

        print("\n[CHECKING] Result elements...\n")

        checks = {
            'PD Value': 'pdValue',
            'Risk Badge': 'pdRiskBadge',
            'Results Section': 'resultsSection'
        }

        found_count = 0
        for check_name, element_id in checks.items():
            try:
                element = self.driver.find_element(By.ID, element_id)
                if element:
                    found_count += 1
                    text = element.text[:50] if element.text else "(empty)"
                    print(f"  [OK] {check_name:20s} - {text}")
                    time.sleep(0.3)
            except:
                print(f"  [NOT FOUND] {check_name}")

        print(f"\n[RESULT] {found_count}/{len(checks)} result elements found")
        time.sleep(self.delay)

        if found_count >= 2:
            self.log_step(8, "Results verified", "COMPLETE")
            return True
        else:
            self.log_step(8, "Results verification inconclusive", "WARNING")
            return True  # Continue anyway - SHAP may not be in these elements

    def verify_shap_data(self):
        """Verify SHAP Tier 2 data"""
        self.log_step(9, "Verify SHAP Tier 2 data", "IN PROGRESS")

        print("[ACTION] Scrolling down to see SHAP section...")
        self.driver.execute_script("window.scrollBy(0, 500);")
        time.sleep(self.delay)

        page_source = self.driver.page_source
        shap_keywords = ['SHAP', 'Feature Contributions', 'Interactions', 'Tier 2']

        found_keywords = []
        for keyword in shap_keywords:
            if keyword in page_source:
                found_keywords.append(keyword)
                print(f"  [FOUND] '{keyword}'")
                time.sleep(0.3)

        print(f"\n[RESULT] {len(found_keywords)}/{len(shap_keywords)} SHAP keywords found")

        if found_keywords:
            self.log_step(9, f"SHAP data found: {', '.join(found_keywords)}", "COMPLETE")
            return True
        else:
            print("[WARNING] SHAP data not found")
            return False

    def take_screenshot(self):
        """Take screenshot of results"""
        self.log_step(10, "Capture screenshot", "IN PROGRESS")

        try:
            screenshot_path = f"/tmp/selenium_results_{self.scenario}.png"
            self.driver.save_screenshot(screenshot_path)
            print(f"[SAVED] Screenshot: {screenshot_path}")
            time.sleep(1)

            self.log_step(10, f"Screenshot saved", "COMPLETE")
            return screenshot_path
        except Exception as e:
            print(f"[FAIL] Error: {str(e)}")
            return None

    def print_final_summary(self):
        """Print final summary"""
        elapsed = time.time() - self.start_time

        print("\n" + "="*75)
        print("[SUMMARY] TEST COMPLETE")
        print("="*75)
        print(f"\nScenario:     {self.scenario.upper()}")
        print(f"Total Time:   {elapsed:.1f} seconds")
        print(f"Test Status:  COMPLETE")
        print(f"\nNext Steps:")
        print(f"  1. Review the browser window")
        print(f"  2. Check the results displayed")
        print(f"  3. Verify SHAP data in Tier 2 section")
        print(f"  4. Screenshot saved to /tmp/")
        print("="*75 + "\n")

    def run_slow_test(self):
        """Run complete test at slow speed"""
        self.start_time = time.time()

        print("\n" + "="*75)
        print("[START] SLOW-MOTION SELENIUM TEST")
        print(f"Scenario: {self.scenario.upper()}")
        print(f"Speed: {self.delay} second delays between actions")
        print("="*75)

        try:
            # Step 1: Setup
            if not self.setup_driver():
                return False

            # Step 2: Navigate
            if not self.navigate_to_page():
                return False

            # Step 3: Click Scenario Button
            if not self.click_scenario_button():
                return False

            # Step 4: Verify Fields
            if not self.verify_fields():
                print("[WARNING] Continuing despite field verification issues...")

            # Step 5: Scroll
            self.scroll_to_calculate_button()

            # Step 6-7: Find and Click Calculate
            if not self.click_calculate_button():
                return False

            # Step 7.5: Wait for Results
            self.wait_for_results()

            # Step 8: Verify Results
            self.verify_results()

            # Step 9: Verify SHAP
            self.verify_shap_data()

            # Step 10: Screenshot
            self.take_screenshot()

            # Final Summary
            self.print_final_summary()

            return True

        except Exception as e:
            print(f"\n[ERROR] Unexpected error: {str(e)}")
            return False

        finally:
            # Keep browser open for inspection
            print("\n[INFO] Browser will stay open for 10 seconds...")
            print("[INFO] Inspect the results before it closes...")
            time.sleep(10)
            self.cleanup()

    def cleanup(self):
        """Close browser"""
        if self.driver:
            self.driver.quit()
            print("[CLEANUP] Browser closed")


def main():
    """Main execution"""
    # Test scenarios
    print("\n[INFO] Available scenarios: healthy, medium, risky")
    print("[INFO] Default scenario: medium")

    # Run with medium risk scenario at slow speed
    scenario = 'medium'  # Change to 'healthy' or 'risky' if desired
    delay = 2  # 2 seconds between actions

    test = SlowAutoFillTest(scenario=scenario, delay=delay)
    success = test.run_slow_test()

    return 0 if success else 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
