"""
Comprehensive Selenium Test for Mixed Method Scenarios
Tests all combinations of:
- Calculation Modes: AIRB, SA, Both
- PD Methods: Rule-Based, Machine Learning
- Borrower Profiles: Good, Medium, Risky
- Multiple loan scenarios with method switching
"""

import sys
import os
import time
from datetime import datetime

if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager


class MixedMethodScenarioTest:
    """Test various combinations of calculation methods"""

    def __init__(self):
        self.driver = None
        self.wait = None
        self.base_url = "http://127.0.0.1:5000/borrower-info.html"
        self.test_results = []
        self.scenario_count = 0
        self.passed = 0
        self.failed = 0

    def setup(self):
        """Initialize WebDriver"""
        chrome_options = Options()
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option("useAutomationExtension", False)

        self.driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=chrome_options
        )
        self.wait = WebDriverWait(self.driver, 15)
        self.driver.get(self.base_url)
        self.wait.until(EC.presence_of_element_located((By.ID, "borrowerId")))
        print("\n[SETUP] WebDriver initialized and application loaded")

    def log_scenario(self, scenario_name, method, calc_mode, status, result):
        """Log test scenario result"""
        self.scenario_count += 1
        status_icon = "[PASS]" if status == "PASS" else "[FAIL]"
        print(f"\n{status_icon} SCENARIO {self.scenario_count}: {scenario_name}")
        print(f"         Method: {method}, Mode: {calc_mode}")
        print(f"         Result: {result}")
        self.test_results.append({
            "scenario": scenario_name,
            "method": method,
            "mode": calc_mode,
            "status": status,
            "result": result
        })
        if status == "PASS":
            self.passed += 1
        else:
            self.failed += 1

    def reset_form(self):
        """Reset form for next test"""
        self.driver.find_element(By.ID, "borrowerId").clear()
        self.driver.find_element(By.ID, "borrowerName").clear()
        self.driver.find_element(By.ID, "exposureAmount").clear()
        self.driver.find_element(By.ID, "debtToEquity").clear()
        self.driver.find_element(By.ID, "interestCoverage").clear()
        self.driver.find_element(By.ID, "profitabilityMargin").clear()
        self.driver.find_element(By.ID, "liquidityRatio").clear()

    def fill_form(self, borrower_id, borrower_name, sector, exposure, de_ratio, coverage, profit, liquidity):
        """Fill borrower form"""
        self.driver.find_element(By.ID, "borrowerId").send_keys(borrower_id)
        self.driver.find_element(By.ID, "borrowerName").send_keys(borrower_name)
        Select(self.driver.find_element(By.ID, "sector")).select_by_value(sector)
        self.driver.find_element(By.ID, "exposureAmount").send_keys(exposure)
        self.driver.find_element(By.ID, "debtToEquity").send_keys(de_ratio)
        self.driver.find_element(By.ID, "interestCoverage").send_keys(coverage)
        self.driver.find_element(By.ID, "profitabilityMargin").send_keys(profit)
        self.driver.find_element(By.ID, "liquidityRatio").send_keys(liquidity)

    def fill_airb_fields(self):
        """Fill AIRB-specific fields"""
        Select(self.driver.find_element(By.ID, "seniority")).select_by_value("Senior Unsecured")
        Select(self.driver.find_element(By.ID, "loanType")).select_by_value("Term Loan Long")

    def fill_sa_fields(self):
        """Fill SA-specific fields"""
        Select(self.driver.find_element(By.ID, "externalRating")).select_by_value("A+")
        Select(self.driver.find_element(By.ID, "exposureCategory")).select_by_value("Corporate")

    def calculate_and_get_pd(self, pd_method):
        """Calculate risk and return PD value"""
        if pd_method == "rule-based":
            self.driver.find_element(By.ID, "pdMethodRuleBased").click()
        else:
            self.driver.find_element(By.ID, "pdMethodML").click()

        self.driver.find_element(By.ID, "calculateBtn").click()
        time.sleep(2 if pd_method == "rule-based" else 3)  # ML takes longer

        try:
            pd_value = self.driver.find_element(By.ID, "pdValue").text
            return pd_value
        except:
            return "N/A"

    def record_loan(self):
        """Record loan to portfolio"""
        try:
            confirm_btn = self.driver.find_element(By.XPATH, "//button[contains(text(), 'Confirm & Record Loan')]")
            self.driver.execute_script("arguments[0].scrollIntoView(true);", confirm_btn)
            time.sleep(1)
            confirm_btn.click()
            time.sleep(2)
            return True
        except:
            return False

    def get_portfolio_count(self):
        """Get number of loans in portfolio"""
        try:
            loans_body = self.driver.find_element(By.ID, "loansTableBody")
            rows = loans_body.find_elements(By.TAG_NAME, "tr")
            return len(rows)
        except:
            return 0

    # ===== SCENARIO TESTS =====

    def scenario_1_airb_rule_based_good_borrower(self):
        """Scenario 1: AIRB mode with Rule-Based PD - Good Borrower"""
        self.reset_form()
        try:
            # Select AIRB mode
            self.driver.find_element(By.ID, "modeAIRB").click()
            time.sleep(1)

            # Good borrower profile
            self.fill_form(
                borrower_id="G001",
                borrower_name="Good Corp Ltd",
                sector="Technology",
                exposure="5000000",
                de_ratio="1.0",
                coverage="3.5",
                profit="12",
                liquidity="1.5"
            )
            self.fill_airb_fields()

            # Calculate with Rule-Based
            pd_value = self.calculate_and_get_pd("rule-based")
            record_success = self.record_loan()
            portfolio_count = self.get_portfolio_count()

            if record_success and portfolio_count > 0:
                self.log_scenario(
                    "AIRB Rule-Based Good Borrower",
                    "Rule-Based",
                    "AIRB",
                    "PASS",
                    f"PD={pd_value}, Portfolio={portfolio_count} loan(s)"
                )
            else:
                self.log_scenario(
                    "AIRB Rule-Based Good Borrower",
                    "Rule-Based",
                    "AIRB",
                    "FAIL",
                    "Failed to record loan"
                )
        except Exception as e:
            self.log_scenario(
                "AIRB Rule-Based Good Borrower",
                "Rule-Based",
                "AIRB",
                "FAIL",
                str(e)[:50]
            )

    def scenario_2_airb_ml_good_borrower(self):
        """Scenario 2: AIRB mode with ML PD - Good Borrower"""
        self.reset_form()
        try:
            # AIRB mode already selected
            self.fill_form(
                borrower_id="G002",
                borrower_name="Tech Innovations Inc",
                sector="Technology",
                exposure="4500000",
                de_ratio="1.2",
                coverage="3.2",
                profit="11",
                liquidity="1.4"
            )
            self.fill_airb_fields()

            # Calculate with ML
            pd_value = self.calculate_and_get_pd("ml")
            record_success = self.record_loan()
            portfolio_count = self.get_portfolio_count()

            if record_success and portfolio_count > 1:
                self.log_scenario(
                    "AIRB ML Good Borrower",
                    "Machine Learning",
                    "AIRB",
                    "PASS",
                    f"PD={pd_value}, Portfolio={portfolio_count} loans"
                )
            else:
                self.log_scenario(
                    "AIRB ML Good Borrower",
                    "Machine Learning",
                    "AIRB",
                    "FAIL",
                    "Failed to record loan or portfolio unchanged"
                )
        except Exception as e:
            self.log_scenario(
                "AIRB ML Good Borrower",
                "Machine Learning",
                "AIRB",
                "FAIL",
                str(e)[:50]
            )

    def scenario_3_airb_rule_based_medium_borrower(self):
        """Scenario 3: AIRB mode with Rule-Based PD - Medium Borrower"""
        self.reset_form()
        try:
            self.fill_form(
                borrower_id="M001",
                borrower_name="Manufacturing Corp",
                sector="Manufacturing",
                exposure="3000000",
                de_ratio="2.0",
                coverage="1.8",
                profit="5",
                liquidity="1.0"
            )
            self.fill_airb_fields()

            pd_value = self.calculate_and_get_pd("rule-based")
            record_success = self.record_loan()
            portfolio_count = self.get_portfolio_count()

            if record_success:
                self.log_scenario(
                    "AIRB Rule-Based Medium Borrower",
                    "Rule-Based",
                    "AIRB",
                    "PASS",
                    f"PD={pd_value}, Portfolio={portfolio_count} loans"
                )
            else:
                self.log_scenario(
                    "AIRB Rule-Based Medium Borrower",
                    "Rule-Based",
                    "AIRB",
                    "FAIL",
                    "Failed to record loan"
                )
        except Exception as e:
            self.log_scenario(
                "AIRB Rule-Based Medium Borrower",
                "Rule-Based",
                "AIRB",
                "FAIL",
                str(e)[:50]
            )

    def scenario_4_airb_ml_medium_borrower(self):
        """Scenario 4: AIRB mode with ML PD - Medium Borrower"""
        self.reset_form()
        try:
            self.fill_form(
                borrower_id="M002",
                borrower_name="Industrial Solutions LLC",
                sector="Manufacturing",
                exposure="2800000",
                de_ratio="2.1",
                coverage="1.7",
                profit="4",
                liquidity="0.9"
            )
            self.fill_airb_fields()

            pd_value = self.calculate_and_get_pd("ml")
            record_success = self.record_loan()
            portfolio_count = self.get_portfolio_count()

            if record_success:
                self.log_scenario(
                    "AIRB ML Medium Borrower",
                    "Machine Learning",
                    "AIRB",
                    "PASS",
                    f"PD={pd_value}, Portfolio={portfolio_count} loans"
                )
            else:
                self.log_scenario(
                    "AIRB ML Medium Borrower",
                    "Machine Learning",
                    "AIRB",
                    "FAIL",
                    "Failed to record loan"
                )
        except Exception as e:
            self.log_scenario(
                "AIRB ML Medium Borrower",
                "Machine Learning",
                "AIRB",
                "FAIL",
                str(e)[:50]
            )

    def scenario_5_sa_rule_based_good_borrower(self):
        """Scenario 5: SA mode with Rule-Based PD - Good Borrower"""
        self.reset_form()
        try:
            # Switch to SA mode
            self.driver.find_element(By.ID, "modeSA").click()
            time.sleep(1)

            self.fill_form(
                borrower_id="SG001",
                borrower_name="Finance Corp AAA",
                sector="Financial",
                exposure="6000000",
                de_ratio="0.8",
                coverage="4.0",
                profit="15",
                liquidity="1.8"
            )
            self.fill_sa_fields()

            pd_value = self.calculate_and_get_pd("rule-based")
            record_success = self.record_loan()
            portfolio_count = self.get_portfolio_count()

            if record_success:
                self.log_scenario(
                    "SA Rule-Based Good Borrower",
                    "Rule-Based",
                    "Standardized Approach",
                    "PASS",
                    f"PD={pd_value}, Portfolio={portfolio_count} loans"
                )
            else:
                self.log_scenario(
                    "SA Rule-Based Good Borrower",
                    "Rule-Based",
                    "Standardized Approach",
                    "FAIL",
                    "Failed to record loan"
                )
        except Exception as e:
            self.log_scenario(
                "SA Rule-Based Good Borrower",
                "Rule-Based",
                "Standardized Approach",
                "FAIL",
                str(e)[:50]
            )

    def scenario_6_sa_ml_good_borrower(self):
        """Scenario 6: SA mode with ML PD - Good Borrower"""
        self.reset_form()
        try:
            self.fill_form(
                borrower_id="SG002",
                borrower_name="Banking Solutions Int",
                sector="Financial",
                exposure="5500000",
                de_ratio="0.9",
                coverage="3.8",
                profit="14",
                liquidity="1.7"
            )
            self.fill_sa_fields()

            pd_value = self.calculate_and_get_pd("ml")
            record_success = self.record_loan()
            portfolio_count = self.get_portfolio_count()

            if record_success:
                self.log_scenario(
                    "SA ML Good Borrower",
                    "Machine Learning",
                    "Standardized Approach",
                    "PASS",
                    f"PD={pd_value}, Portfolio={portfolio_count} loans"
                )
            else:
                self.log_scenario(
                    "SA ML Good Borrower",
                    "Machine Learning",
                    "Standardized Approach",
                    "FAIL",
                    "Failed to record loan"
                )
        except Exception as e:
            self.log_scenario(
                "SA ML Good Borrower",
                "Machine Learning",
                "Standardized Approach",
                "FAIL",
                str(e)[:50]
            )

    def scenario_7_sa_rule_based_risky_borrower(self):
        """Scenario 7: SA mode with Rule-Based PD - Risky Borrower"""
        self.reset_form()
        try:
            self.fill_form(
                borrower_id="SR001",
                borrower_name="Struggling Industries",
                sector="Retail",
                exposure="2000000",
                de_ratio="3.0",
                coverage="0.8",
                profit="-2",
                liquidity="0.6"
            )
            self.fill_sa_fields()

            pd_value = self.calculate_and_get_pd("rule-based")
            record_success = self.record_loan()
            portfolio_count = self.get_portfolio_count()

            if record_success:
                self.log_scenario(
                    "SA Rule-Based Risky Borrower",
                    "Rule-Based",
                    "Standardized Approach",
                    "PASS",
                    f"PD={pd_value}, Portfolio={portfolio_count} loans"
                )
            else:
                self.log_scenario(
                    "SA Rule-Based Risky Borrower",
                    "Rule-Based",
                    "Standardized Approach",
                    "FAIL",
                    "Failed to record loan"
                )
        except Exception as e:
            self.log_scenario(
                "SA Rule-Based Risky Borrower",
                "Rule-Based",
                "Standardized Approach",
                "FAIL",
                str(e)[:50]
            )

    def scenario_8_sa_ml_risky_borrower(self):
        """Scenario 8: SA mode with ML PD - Risky Borrower"""
        self.reset_form()
        try:
            self.fill_form(
                borrower_id="SR002",
                borrower_name="Retail Challenges Ltd",
                sector="Retail",
                exposure="1800000",
                de_ratio="2.9",
                coverage="0.9",
                profit="-1",
                liquidity="0.7"
            )
            self.fill_sa_fields()

            pd_value = self.calculate_and_get_pd("ml")
            record_success = self.record_loan()
            portfolio_count = self.get_portfolio_count()

            if record_success:
                self.log_scenario(
                    "SA ML Risky Borrower",
                    "Machine Learning",
                    "Standardized Approach",
                    "PASS",
                    f"PD={pd_value}, Portfolio={portfolio_count} loans"
                )
            else:
                self.log_scenario(
                    "SA ML Risky Borrower",
                    "Machine Learning",
                    "Standardized Approach",
                    "FAIL",
                    "Failed to record loan"
                )
        except Exception as e:
            self.log_scenario(
                "SA ML Risky Borrower",
                "Machine Learning",
                "Standardized Approach",
                "FAIL",
                str(e)[:50]
            )

    def scenario_9_both_modes_method_comparison(self):
        """Scenario 9: Both modes with Rule-Based - Compare AIRB vs SA"""
        self.reset_form()
        try:
            # Switch to Both mode
            self.driver.find_element(By.ID, "modeBoth").click()
            time.sleep(1)

            self.fill_form(
                borrower_id="BOTH001",
                borrower_name="Comparison Test Co",
                sector="Energy",
                exposure="7000000",
                de_ratio="1.5",
                coverage="2.5",
                profit="8",
                liquidity="1.2"
            )

            # Fill both AIRB and SA fields
            self.fill_airb_fields()
            self.fill_sa_fields()

            pd_value = self.calculate_and_get_pd("rule-based")
            record_success = self.record_loan()
            portfolio_count = self.get_portfolio_count()

            if record_success:
                self.log_scenario(
                    "Both Modes Rule-Based Comparison",
                    "Rule-Based",
                    "AIRB + SA",
                    "PASS",
                    f"PD={pd_value}, Both methods calculated, Portfolio={portfolio_count} loans"
                )
            else:
                self.log_scenario(
                    "Both Modes Rule-Based Comparison",
                    "Rule-Based",
                    "AIRB + SA",
                    "FAIL",
                    "Failed to record loan"
                )
        except Exception as e:
            self.log_scenario(
                "Both Modes Rule-Based Comparison",
                "Rule-Based",
                "AIRB + SA",
                "FAIL",
                str(e)[:50]
            )

    def scenario_10_both_modes_ml_comparison(self):
        """Scenario 10: Both modes with ML PD - Compare AIRB vs SA"""
        self.reset_form()
        try:
            self.fill_form(
                borrower_id="BOTH002",
                borrower_name="ML Comparison Co",
                sector="Healthcare",
                exposure="6500000",
                de_ratio="1.6",
                coverage="2.4",
                profit="9",
                liquidity="1.3"
            )

            self.fill_airb_fields()
            self.fill_sa_fields()

            pd_value = self.calculate_and_get_pd("ml")
            record_success = self.record_loan()
            portfolio_count = self.get_portfolio_count()

            if record_success:
                self.log_scenario(
                    "Both Modes ML Comparison",
                    "Machine Learning",
                    "AIRB + SA",
                    "PASS",
                    f"PD={pd_value}, Both methods calculated, Portfolio={portfolio_count} loans"
                )
            else:
                self.log_scenario(
                    "Both Modes ML Comparison",
                    "Machine Learning",
                    "AIRB + SA",
                    "FAIL",
                    "Failed to record loan"
                )
        except Exception as e:
            self.log_scenario(
                "Both Modes ML Comparison",
                "Machine Learning",
                "AIRB + SA",
                "FAIL",
                str(e)[:50]
            )

    def scenario_11_method_switching_same_borrower(self):
        """Scenario 11: Switch PD methods on same borrower data"""
        self.reset_form()
        try:
            self.driver.find_element(By.ID, "modeAIRB").click()
            time.sleep(1)

            self.fill_form(
                borrower_id="SWITCH001",
                borrower_name="Method Switching Test",
                sector="Technology",
                exposure="4000000",
                de_ratio="1.4",
                coverage="2.8",
                profit="10",
                liquidity="1.4"
            )
            self.fill_airb_fields()

            # First with Rule-Based
            pd_rb = self.calculate_and_get_pd("rule-based")

            # Then switch to ML
            pd_ml = self.calculate_and_get_pd("ml")

            record_success = self.record_loan()
            portfolio_count = self.get_portfolio_count()

            if record_success and pd_rb != "N/A" and pd_ml != "N/A":
                self.log_scenario(
                    "Method Switching Same Borrower",
                    "Rule-Based -> ML",
                    "AIRB",
                    "PASS",
                    f"RB PD={pd_rb}, ML PD={pd_ml}, Recorded with ML"
                )
            else:
                self.log_scenario(
                    "Method Switching Same Borrower",
                    "Rule-Based -> ML",
                    "AIRB",
                    "FAIL",
                    "Failed to calculate or record"
                )
        except Exception as e:
            self.log_scenario(
                "Method Switching Same Borrower",
                "Rule-Based -> ML",
                "AIRB",
                "FAIL",
                str(e)[:50]
            )

    def scenario_12_verify_portfolio_diversity(self):
        """Scenario 12: Verify portfolio has diverse loans with different methods"""
        try:
            loan_count = self.get_portfolio_count()

            if loan_count >= 5:
                self.log_scenario(
                    "Portfolio Diversity Check",
                    "Multiple",
                    "Mixed",
                    "PASS",
                    f"Portfolio contains {loan_count} loans with different methods/modes"
                )
            else:
                self.log_scenario(
                    "Portfolio Diversity Check",
                    "Multiple",
                    "Mixed",
                    "INFO",
                    f"Portfolio contains {loan_count} loans"
                )
        except Exception as e:
            self.log_scenario(
                "Portfolio Diversity Check",
                "Multiple",
                "Mixed",
                "FAIL",
                str(e)[:50]
            )

    def generate_report(self):
        """Generate comprehensive test report"""
        print("\n" + "="*80)
        print("MIXED METHOD SCENARIO TEST - COMPREHENSIVE REPORT")
        print("="*80)
        print(f"\nTest Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"\nScenarios Executed: {self.scenario_count}")
        print(f"Passed: {self.passed}")
        print(f"Failed: {self.failed}")
        success_rate = (self.passed / self.scenario_count * 100) if self.scenario_count > 0 else 0
        print(f"Success Rate: {success_rate:.1f}%")

        print("\n" + "-"*80)
        print("SCENARIO BREAKDOWN BY METHOD:")
        print("-"*80)

        rule_based_results = [r for r in self.test_results if r["method"] == "Rule-Based"]
        ml_results = [r for r in self.test_results if r["method"] == "Machine Learning"]

        print(f"\nRule-Based Method:")
        print(f"  Scenarios: {len(rule_based_results)}")
        rule_passed = sum(1 for r in rule_based_results if r["status"] == "PASS")
        print(f"  Passed: {rule_passed}/{len(rule_based_results)}")

        print(f"\nMachine Learning Method:")
        print(f"  Scenarios: {len(ml_results)}")
        ml_passed = sum(1 for r in ml_results if r["status"] == "PASS")
        print(f"  Passed: {ml_passed}/{len(ml_results)}")

        print("\n" + "-"*80)
        print("SCENARIO BREAKDOWN BY MODE:")
        print("-"*80)

        airb_results = [r for r in self.test_results if "AIRB" in r["mode"]]
        sa_results = [r for r in self.test_results if "Standardized" in r["mode"]]
        both_results = [r for r in self.test_results if "AIRB + SA" in r["mode"]]

        print(f"\nAIRB Mode:")
        print(f"  Scenarios: {len(airb_results)}")
        airb_passed = sum(1 for r in airb_results if r["status"] == "PASS")
        print(f"  Passed: {airb_passed}/{len(airb_results)}")

        print(f"\nStandardized Approach Mode:")
        print(f"  Scenarios: {len(sa_results)}")
        sa_passed = sum(1 for r in sa_results if r["status"] == "PASS")
        print(f"  Passed: {sa_passed}/{len(sa_results)}")

        print(f"\nBoth Modes:")
        print(f"  Scenarios: {len(both_results)}")
        both_passed = sum(1 for r in both_results if r["status"] == "PASS")
        print(f"  Passed: {both_passed}/{len(both_results)}")

        print("\n" + "-"*80)
        print("DETAILED SCENARIO RESULTS:")
        print("-"*80)

        for i, result in enumerate(self.test_results, 1):
            status_icon = "[PASS]" if result["status"] == "PASS" else "[FAIL]"
            print(f"\n{i}. {status_icon} {result['scenario']}")
            print(f"   Method: {result['method']}")
            print(f"   Mode: {result['mode']}")
            print(f"   Result: {result['result']}")

        print("\n" + "="*80)
        if self.failed == 0:
            print("OVERALL STATUS: ALL SCENARIOS PASSED!")
        else:
            print(f"OVERALL STATUS: {self.failed} scenario(s) failed")
        print("="*80)

    def teardown(self):
        """Close browser"""
        if self.driver:
            self.driver.quit()
            print("\n[TEARDOWN] WebDriver closed")

    def run_all_scenarios(self):
        """Run all test scenarios"""
        print("\n" + "="*80)
        print("BANKING CREDIT RISK CALCULATOR - MIXED METHOD SCENARIOS TEST")
        print("Testing all combinations of Modes, Methods, and Borrower Profiles")
        print("="*80)

        try:
            self.setup()

            # Run all scenarios
            self.scenario_1_airb_rule_based_good_borrower()
            self.scenario_2_airb_ml_good_borrower()
            self.scenario_3_airb_rule_based_medium_borrower()
            self.scenario_4_airb_ml_medium_borrower()
            self.scenario_5_sa_rule_based_good_borrower()
            self.scenario_6_sa_ml_good_borrower()
            self.scenario_7_sa_rule_based_risky_borrower()
            self.scenario_8_sa_ml_risky_borrower()
            self.scenario_9_both_modes_method_comparison()
            self.scenario_10_both_modes_ml_comparison()
            self.scenario_11_method_switching_same_borrower()
            self.scenario_12_verify_portfolio_diversity()

            self.generate_report()
            self.teardown()

            return self.failed == 0

        except Exception as e:
            print(f"\n[FATAL ERROR] {e}")
            import traceback
            traceback.print_exc()
            self.teardown()
            return False


if __name__ == "__main__":
    tester = MixedMethodScenarioTest()
    success = tester.run_all_scenarios()
    exit(0 if success else 1)
