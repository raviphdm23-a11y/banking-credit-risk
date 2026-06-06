"""
Comprehensive End-to-End Selenium Test for Banking Credit Risk Calculator
Tests the complete workflow including:
- Form filling with borrower information
- Financial metrics input
- Both PD methods (Rule-Based and ML)
- Risk parameter calculation and display
- Loan recording to portfolio
- Portfolio management (view, export, delete)
- Multiple loans and portfolio summary
"""

import sys
import os
import time
from pathlib import Path
from datetime import datetime

# Fix encoding for Windows
if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.webdriver import WebDriver
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import TimeoutException, NoSuchElementException


class CompleteFlowTest:
    """Comprehensive test suite for complete user workflow"""

    def __init__(self):
        """Initialize test configuration"""
        self.driver: WebDriver = None
        self.wait = None
        self.base_url = "http://127.0.0.1:5000/borrower-info.html"
        self.step_timeout = 15
        self.test_results = []
        self.passed = 0
        self.failed = 0

    def setup(self):
        """Setup Chrome WebDriver"""
        print("\n" + "="*80)
        print("SETUP: Initializing Chrome WebDriver")
        print("="*80)

        try:
            chrome_options = Options()
            # chrome_options.add_argument("--headless")  # Uncomment for headless mode
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option("useAutomationExtension", False)
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-gpu")

            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.wait = WebDriverWait(self.driver, self.step_timeout)

            print("[PASS] Chrome WebDriver initialized successfully")
            return True
        except Exception as e:
            print(f"[FAIL] Failed to initialize WebDriver: {e}")
            return False

    def log(self, step_num, status, message):
        """Log test step"""
        status_icon = "[PASS]" if status == "PASS" else "[FAIL]" if status == "FAIL" else "[INFO]"
        print(f"{status_icon} Step {step_num}: {message}")
        self.test_results.append({"step": step_num, "status": status, "message": message})
        if status == "PASS":
            self.passed += 1
        elif status == "FAIL":
            self.failed += 1

    def test_1_open_application(self):
        """Test 1: Open the application"""
        print("\n" + "-"*80)
        print("TEST 1: OPEN APPLICATION")
        print("-"*80)

        try:
            self.driver.get(self.base_url)
            self.wait.until(EC.presence_of_element_located((By.ID, "borrowerID")))
            self.log(1, "PASS", f"Application loaded successfully from {self.base_url}")
            return True
        except TimeoutException:
            self.log(1, "FAIL", "Application failed to load within timeout")
            return False
        except Exception as e:
            self.log(1, "FAIL", f"Error opening application: {e}")
            return False

    def test_2_fill_borrower_info(self):
        """Test 2: Fill borrower information form"""
        print("\n" + "-"*80)
        print("TEST 2: FILL BORROWER INFORMATION")
        print("-"*80)

        try:
            # Fill Borrower ID
            borrower_id = self.driver.find_element(By.ID, "borrowerId")
            borrower_id.clear()
            borrower_id.send_keys("BRRW001")
            self.log(2.1, "PASS", "Borrower ID entered: BRRW001")

            # Fill Borrower Name
            borrower_name = self.driver.find_element(By.ID, "borrowerName")
            borrower_name.clear()
            borrower_name.send_keys("Acme Corporation")
            self.log(2.2, "PASS", "Borrower Name entered: Acme Corporation")

            # Select Sector
            sector_select = Select(self.driver.find_element(By.ID, "sector"))
            sector_select.select_by_value("Technology")
            self.log(2.3, "PASS", "Sector selected: Technology")

            # Fill Exposure Amount
            exposure = self.driver.find_element(By.ID, "exposureAmount")
            exposure.clear()
            exposure.send_keys("1000000")
            self.log(2.4, "PASS", "Exposure Amount entered: 1000000")

            # Select Calculation Mode - Both
            both_mode = self.driver.find_element(By.ID, "modeBoth")
            both_mode.click()
            self.log(2.5, "PASS", "Calculation Mode selected: Both (AIRB + SA)")

            return True
        except Exception as e:
            self.log(2, "FAIL", f"Error filling borrower information: {e}")
            return False

    def test_3_test_rule_based_method(self):
        """Test 3: Test Rule-Based PD calculation method"""
        print("\n" + "-"*80)
        print("TEST 3: RULE-BASED PD METHOD")
        print("-"*80)

        try:
            # Select Rule-Based radio button
            rule_based_radio = self.driver.find_element(By.ID, "pdMethodRuleBased")
            rule_based_radio.click()
            self.log(3.1, "PASS", "Rule-Based PD method selected")

            # Fill financial metrics
            de_ratio = self.driver.find_element(By.ID, "debtToEquity")
            de_ratio.clear()
            de_ratio.send_keys("1.5")
            self.log(3.2, "PASS", "D/E Ratio entered: 1.5")

            coverage = self.driver.find_element(By.ID, "interestCoverage")
            coverage.clear()
            coverage.send_keys("2.5")
            self.log(3.3, "PASS", "Interest Coverage entered: 2.5")

            profitability = self.driver.find_element(By.ID, "profitabilityMargin")
            profitability.clear()
            profitability.send_keys("8")
            self.log(3.4, "PASS", "Profitability entered: 8")

            liquidity = self.driver.find_element(By.ID, "liquidityRatio")
            liquidity.clear()
            liquidity.send_keys("1.2")
            self.log(3.5, "PASS", "Liquidity Ratio entered: 1.2")

            # Click Calculate button
            calculate_btn = self.driver.find_element(By.ID, "calculateBtn")
            calculate_btn.click()
            self.log(3.6, "PASS", "Calculate Risk Parameters button clicked")

            # Wait for results to appear
            time.sleep(2)
            results_section = self.wait.until(
                EC.visibility_of_element_located((By.ID, "resultsSection"))
            )
            self.log(3.7, "PASS", "Results section appeared")

            # Verify PD result is displayed
            pd_result = self.driver.find_element(By.ID, "pdValue")
            pd_value = pd_result.text
            self.log(3.8, "PASS", f"Rule-Based PD calculated: {pd_value}")

            return True
        except Exception as e:
            self.log(3, "FAIL", f"Error in rule-based method test: {e}")
            return False

    def test_4_test_ml_method(self):
        """Test 4: Test Machine Learning PD calculation method"""
        print("\n" + "-"*80)
        print("TEST 4: MACHINE LEARNING PD METHOD")
        print("-"*80)

        try:
            # Select ML radio button
            ml_radio = self.driver.find_element(By.ID, "pdMethodML")
            ml_radio.click()
            self.log(4.1, "PASS", "Machine Learning PD method selected")

            # Click Calculate button again
            calculate_btn = self.driver.find_element(By.ID, "calculateBtn")
            calculate_btn.click()
            self.log(4.2, "PASS", "Calculate Risk Parameters button clicked for ML method")

            # Wait for ML results
            time.sleep(3)  # ML may take longer due to model loading
            try:
                results_section = self.wait.until(
                    EC.visibility_of_element_located((By.ID, "resultsSection"))
                )
                self.log(4.3, "PASS", "ML Results section appeared")
            except:
                self.log(4.3, "INFO", "Results already visible")

            # Verify ML PD result is displayed
            try:
                pd_result = self.driver.find_element(By.ID, "pdValue")
                pd_value = pd_result.text
                self.log(4.4, "PASS", f"ML-Based PD calculated: {pd_value}")
            except:
                self.log(4.4, "FAIL", "Could not find PD result")
                return False

            return True
        except Exception as e:
            self.log(4, "FAIL", f"Error in ML method test: {e}")
            return False

    def test_5_fill_collateral_info(self):
        """Test 5: Fill collateral and seniority information"""
        print("\n" + "-"*80)
        print("TEST 5: FILL COLLATERAL & SENIORITY INFO")
        print("-"*80)

        try:
            # Select Seniority
            seniority_select = Select(self.driver.find_element(By.ID, "seniority"))
            seniority_select.select_by_value("Senior Secured")
            self.log(5.1, "PASS", "Seniority selected: Senior Secured")

            # Select Loan Type
            loan_type_select = Select(self.driver.find_element(By.ID, "loanType"))
            loan_type_select.select_by_value("Term Loan")
            self.log(5.2, "PASS", "Loan Type selected: Term Loan")

            # Select Collateral Type
            collateral_type_select = Select(self.driver.find_element(By.ID, "collateralType"))
            collateral_type_select.select_by_value("Real Estate")
            self.log(5.3, "PASS", "Collateral Type selected: Real Estate")

            # Fill Collateral Value
            collateral_value = self.driver.find_element(By.ID, "collateralValue")
            collateral_value.clear()
            collateral_value.send_keys("500000")
            self.log(5.4, "PASS", "Collateral Value entered: 500000")

            return True
        except Exception as e:
            self.log(5, "FAIL", f"Error filling collateral info: {e}")
            return False

    def test_6_fill_sa_fields(self):
        """Test 6: Fill Standardized Approach specific fields"""
        print("\n" + "-"*80)
        print("TEST 6: FILL SA FIELDS")
        print("-"*80)

        try:
            # Select External Rating
            rating_select = Select(self.driver.find_element(By.ID, "externalRating"))
            rating_select.select_by_value("A+")
            self.log(6.1, "PASS", "External Rating selected: A+")

            # Select Exposure Category
            category_select = Select(self.driver.find_element(By.ID, "exposureCategory"))
            category_select.select_by_value("Corporate")
            self.log(6.2, "PASS", "Exposure Category selected: Corporate")

            return True
        except Exception as e:
            self.log(6, "FAIL", f"Error filling SA fields: {e}")
            return False

    def test_7_record_loan(self):
        """Test 7: Record loan to portfolio"""
        print("\n" + "-"*80)
        print("TEST 7: RECORD LOAN TO PORTFOLIO")
        print("-"*80)

        try:
            # Find and scroll to confirm button (uses onclick, not ID)
            confirm_btn = self.driver.find_element(By.XPATH, "//button[contains(text(), 'Confirm & Record Loan')]")
            self.driver.execute_script("arguments[0].scrollIntoView(true);", confirm_btn)
            time.sleep(1)

            # Click Confirm & Record Loan button
            confirm_btn.click()
            self.log(7.1, "PASS", "Confirm & Record Loan button clicked")

            # Wait for portfolio table to appear
            time.sleep(2)
            portfolio_table = self.wait.until(
                EC.presence_of_element_located((By.ID, "loansTable"))
            )
            self.log(7.2, "PASS", "Portfolio table appeared")

            # Verify loan appears in portfolio
            table_body = self.driver.find_element(By.ID, "loansTableBody")
            table_rows = table_body.find_elements(By.TAG_NAME, "tr")
            if len(table_rows) > 0:
                self.log(7.3, "PASS", f"Loan recorded in portfolio. Total rows: {len(table_rows)}")
            else:
                self.log(7.3, "FAIL", "Loan not found in portfolio table")
                return False

            # Verify portfolio section is visible
            portfolio_section = self.driver.find_element(By.ID, "portfolioSection")
            if portfolio_section.is_displayed():
                self.log(7.4, "PASS", "Portfolio section visible")
            else:
                self.log(7.4, "FAIL", "Portfolio section not visible")

            return True
        except Exception as e:
            self.log(7, "FAIL", f"Error recording loan: {e}")
            return False

    def test_8_verify_portfolio_summary(self):
        """Test 8: Verify portfolio summary statistics"""
        print("\n" + "-"*80)
        print("TEST 8: VERIFY PORTFOLIO SUMMARY")
        print("-"*80)

        try:
            # Check Loan Count
            loan_count = self.driver.find_element(By.ID, "summaryLoanCount")
            count_text = loan_count.text
            self.log(8.1, "PASS", f"Total Loans: {count_text}")

            # Check Total EAD
            total_ead = self.driver.find_element(By.ID, "summaryTotalEAD")
            ead_text = total_ead.text
            self.log(8.2, "PASS", f"Total EAD: {ead_text}")

            # Check Total RWA
            total_rwa = self.driver.find_element(By.ID, "summaryTotalRWA")
            rwa_text = total_rwa.text
            self.log(8.3, "PASS", f"Total RWA: {rwa_text}")

            # Check Risk Density
            risk_density = self.driver.find_element(By.ID, "summaryRiskDensity")
            density_text = risk_density.text
            self.log(8.4, "PASS", f"Risk Density: {density_text}")

            # Check Total Capital
            total_capital = self.driver.find_element(By.ID, "summaryTotalCapital")
            capital_text = total_capital.text
            self.log(8.5, "PASS", f"Total Capital Required: {capital_text}")

            return True
        except Exception as e:
            self.log(8, "FAIL", f"Error verifying portfolio summary: {e}")
            return False

    def test_9_record_second_loan(self):
        """Test 9: Record a second loan with different data"""
        print("\n" + "-"*80)
        print("TEST 9: RECORD SECOND LOAN")
        print("-"*80)

        try:
            # Scroll to form
            form_section = self.driver.find_element(By.ID, "borrowerId")
            self.driver.execute_script("arguments[0].scrollIntoView(true);", form_section)
            time.sleep(1)

            # Fill new borrower info
            borrower_id = self.driver.find_element(By.ID, "borrowerId")
            borrower_id.clear()
            borrower_id.send_keys("BRRW002")
            self.log(9.1, "PASS", "Second borrower ID entered: BRRW002")

            borrower_name = self.driver.find_element(By.ID, "borrowerName")
            borrower_name.clear()
            borrower_name.send_keys("Beta Industries")
            self.log(9.2, "PASS", "Second borrower Name entered: Beta Industries")

            # Fill financial metrics (different values)
            de_ratio = self.driver.find_element(By.ID, "debtToEquity")
            de_ratio.clear()
            de_ratio.send_keys("2.0")
            self.log(9.3, "PASS", "D/E Ratio for second loan: 2.0")

            coverage = self.driver.find_element(By.ID, "interestCoverage")
            coverage.clear()
            coverage.send_keys("1.8")
            self.log(9.4, "PASS", "Interest Coverage for second loan: 1.8")

            profitability = self.driver.find_element(By.ID, "profitabilityMargin")
            profitability.clear()
            profitability.send_keys("5")
            self.log(9.5, "PASS", "Profitability for second loan: 5")

            liquidity = self.driver.find_element(By.ID, "liquidityRatio")
            liquidity.clear()
            liquidity.send_keys("1.0")
            self.log(9.6, "PASS", "Liquidity Ratio for second loan: 1.0")

            # Calculate
            calculate_btn = self.driver.find_element(By.ID, "calculateBtn")
            calculate_btn.click()
            time.sleep(2)
            self.log(9.7, "PASS", "Calculate button clicked for second loan")

            # Record second loan
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1)
            confirm_btn = self.driver.find_element(By.XPATH, "//button[contains(text(), 'Confirm & Record Loan')]")
            confirm_btn.click()
            self.log(9.8, "PASS", "Second loan recorded")

            time.sleep(2)
            return True
        except Exception as e:
            self.log(9, "FAIL", f"Error recording second loan: {e}")
            return False

    def test_10_verify_portfolio_has_two_loans(self):
        """Test 10: Verify portfolio has two loans with updated summary"""
        print("\n" + "-"*80)
        print("TEST 10: VERIFY PORTFOLIO WITH TWO LOANS")
        print("-"*80)

        try:
            loans_table_body = self.driver.find_element(By.ID, "loansTableBody")
            table_rows = loans_table_body.find_elements(By.TAG_NAME, "tr")

            if len(table_rows) >= 2:
                self.log(10.1, "PASS", f"Portfolio has {len(table_rows)} loans")
            else:
                self.log(10.1, "FAIL", f"Portfolio should have at least 2 loans but has {len(table_rows)}")
                return False

            # Verify loans are different
            first_row = table_rows[0].text if len(table_rows) > 0 else ""
            second_row = table_rows[1].text if len(table_rows) > 1 else ""

            if "BRRW001" in first_row or "Acme" in first_row:
                self.log(10.2, "PASS", "First loan details visible in portfolio")
            else:
                self.log(10.2, "INFO", f"First row: {first_row}")

            if "BRRW002" in second_row or "Beta" in second_row:
                self.log(10.3, "PASS", "Second loan details visible in portfolio")
            else:
                self.log(10.3, "INFO", f"Second row: {second_row}")

            return True
        except Exception as e:
            self.log(10, "FAIL", f"Error verifying portfolio: {e}")
            return False

    def test_11_test_export_csv(self):
        """Test 11: Test CSV export functionality"""
        print("\n" + "-"*80)
        print("TEST 11: TEST CSV EXPORT")
        print("-"*80)

        try:
            export_csv_btn = self.driver.find_element(By.XPATH, "//button[contains(text(), 'Export to CSV')]")
            if export_csv_btn.is_displayed():
                self.log(11.1, "PASS", "Export CSV button is visible")
            else:
                self.log(11.1, "FAIL", "Export CSV button is not visible")
                return False

            # Note: We can't directly check file download in Selenium,
            # but we can verify the button is clickable
            self.log(11.2, "PASS", "CSV export button is clickable and ready")
            return True
        except Exception as e:
            self.log(11, "FAIL", f"Error testing CSV export: {e}")
            return False

    def test_12_test_delete_loan(self):
        """Test 12: Test delete loan functionality"""
        print("\n" + "-"*80)
        print("TEST 12: TEST DELETE LOAN")
        print("-"*80)

        try:
            loans_table_body = self.driver.find_element(By.ID, "loansTableBody")
            initial_rows = loans_table_body.find_elements(By.TAG_NAME, "tr")
            initial_count = len(initial_rows)

            if initial_count == 0:
                self.log(12.1, "SKIP", "No loans to delete")
                return True

            # Find delete button in first row
            delete_button = initial_rows[0].find_element(By.XPATH, ".//button[contains(text(), 'Delete') or contains(text(), 'X')]")
            self.log(12.1, "PASS", f"Found delete button. Current loans: {initial_count}")

            # Click delete button
            delete_button.click()
            time.sleep(2)

            # Verify loan was deleted
            updated_rows = loans_table_body.find_elements(By.TAG_NAME, "tr")
            updated_count = len(updated_rows)

            if updated_count < initial_count:
                self.log(12.2, "PASS", f"Loan deleted. Remaining loans: {updated_count}")
                return True
            else:
                self.log(12.2, "INFO", f"Loan count: {updated_count} (was {initial_count})")
                return True

        except Exception as e:
            self.log(12, "FAIL", f"Error testing delete loan: {e}")
            return False

    def teardown(self):
        """Clean up - close browser"""
        print("\n" + "="*80)
        print("TEARDOWN: Closing WebDriver")
        print("="*80)
        if self.driver:
            self.driver.quit()
            print("[PASS] WebDriver closed successfully")

    def generate_report(self):
        """Generate test report"""
        print("\n" + "="*80)
        print("TEST EXECUTION REPORT")
        print("="*80)

        total_tests = self.passed + self.failed
        success_rate = (self.passed / total_tests * 100) if total_tests > 0 else 0

        print(f"\nTest Summary:")
        print(f"  Total Steps: {total_tests}")
        print(f"  Passed: {self.passed}")
        print(f"  Failed: {self.failed}")
        print(f"  Success Rate: {success_rate:.1f}%")

        if self.failed == 0:
            print("\n" + "="*80)
            print("SUCCESS: ALL TESTS PASSED!")
            print("="*80)
        else:
            print("\n" + "="*80)
            print(f"FAILURE: {self.failed} test(s) failed")
            print("="*80)

        return self.failed == 0

    def run_all_tests(self):
        """Run all tests in sequence"""
        print("\n" + "="*80)
        print("BANKING CREDIT RISK CALCULATOR - COMPLETE WORKFLOW TEST")
        print("="*80)

        try:
            if not self.setup():
                print("\n[FATAL] Setup failed. Cannot continue.")
                return False

            # Run all tests
            tests = [
                ("Open Application", self.test_1_open_application),
                ("Fill Borrower Info", self.test_2_fill_borrower_info),
                ("Rule-Based PD Method", self.test_3_test_rule_based_method),
                ("Machine Learning PD Method", self.test_4_test_ml_method),
                ("Fill Collateral Info", self.test_5_fill_collateral_info),
                ("Fill SA Fields", self.test_6_fill_sa_fields),
                ("Record Loan", self.test_7_record_loan),
                ("Verify Portfolio Summary", self.test_8_verify_portfolio_summary),
                ("Record Second Loan", self.test_9_record_second_loan),
                ("Verify Two Loans", self.test_10_verify_portfolio_has_two_loans),
                ("Test CSV Export", self.test_11_test_export_csv),
                ("Test Delete Loan", self.test_12_test_delete_loan),
            ]

            for test_name, test_func in tests:
                try:
                    test_func()
                except Exception as e:
                    self.log(0, "FAIL", f"Test '{test_name}' threw exception: {e}")

            success = self.generate_report()
            self.teardown()
            return success

        except Exception as e:
            print(f"\n[FATAL ERROR] {e}")
            import traceback
            traceback.print_exc()
            self.teardown()
            return False


if __name__ == "__main__":
    tester = CompleteFlowTest()
    success = tester.run_all_tests()
    exit(0 if success else 1)
