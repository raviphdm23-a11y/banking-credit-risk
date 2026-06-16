"""
Smoke tests for the Banking Credit Risk Calculator consumer UI.
Designed to be called programmatically from the Flask admin API.
Returns structured JSON-serialisable results.
"""

import time
import traceback

def run_smoke_tests(base_url='http://127.0.0.1:5000'):
    """
    Run headless Selenium smoke tests against the live Flask app.
    Returns a dict with per-test results and an overall summary.
    """
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import Select, WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from webdriver_manager.chrome import ChromeDriverManager

    results = []
    driver = None
    suite_start = time.time()

    def record(name, passed, error=None, duration=None):
        results.append({
            'name': name,
            'passed': passed,
            'error': error,
            'duration_seconds': round(duration, 2) if duration is not None else None
        })

    def step(name, fn):
        t0 = time.time()
        try:
            fn()
            record(name, True, duration=time.time() - t0)
            return True
        except Exception as e:
            record(name, False, error=str(e), duration=time.time() - t0)
            return False

    def fill(field_id, value):
        el = driver.find_element(By.ID, field_id)
        el.clear()
        el.send_keys(str(value))

    def choose(select_id, value):
        Select(driver.find_element(By.ID, select_id)).select_by_value(str(value))

    # ── Setup headless Chrome ────────────────────────────────────────────────
    opts = Options()
    opts.add_argument('--headless')
    opts.add_argument('--disable-gpu')
    opts.add_argument('--no-sandbox')
    opts.add_argument('--window-size=1280,900')
    opts.add_argument('--disable-blink-features=AutomationControlled')
    opts.add_experimental_option('excludeSwitches', ['enable-automation'])

    try:
        driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=opts
        )
        wait = WebDriverWait(driver, 15)
    except Exception as e:
        return {
            'status': 'error',
            'error': f'Chrome driver setup failed: {e}',
            'tests': [],
            'summary': {'total': 0, 'passed': 0, 'failed': 0, 'duration_seconds': 0}
        }

    try:
        # ── TC-01: Home page loads ───────────────────────────────────────────
        def tc01():
            driver.get(f'{base_url}/')
            wait.until(EC.presence_of_element_located((By.TAG_NAME, 'body')))
            assert driver.title, 'Page has no title'
        step('TC-01: Home page loads', tc01)

        # ── TC-02: Calculator page loads ─────────────────────────────────────
        def tc02():
            driver.get(f'{base_url}/borrower-info.html')
            wait.until(EC.presence_of_element_located((By.ID, 'borrowerId')))
            wait.until(EC.presence_of_element_located((By.ID, 'calculateBtn')))
            # Confirm new KYC section is present
            assert driver.find_element(By.ID, 'kycAge'), 'KYC section not found'
            assert driver.find_element(By.ID, 'kycCibilScore'), 'CIBIL field not found'
        step('TC-02: Calculator page loads with KYC section', tc02)

        # ── TC-03: Full form accepts valid input (Step 1 + 2 KYC + 3 Financial + 4a AIRB) ──
        def tc03():
            # Step 1 — Borrower Info
            fill('borrowerId', 'SMOKE001')
            fill('borrowerName', 'Tata Steel Ltd')
            choose('sector', 'Manufacturing')
            fill('exposureAmount', '10000000')
            driver.execute_script(
                'arguments[0].click()',
                driver.find_element(By.ID, 'modeAIRB')
            )
            time.sleep(0.3)

            # Step 2 — Borrower Profile (KYC)
            fill('kycAge', '38')
            choose('kycEmploymentType', '4')       # Business Owner
            fill('kycYearsEmployed', '10')
            fill('kycAnnualIncome', '1200000')
            fill('kycFoir', '0.35')
            fill('kycNumDependents', '2')
            choose('kycCityTier', '1')             # Tier 1
            choose('kycEducation', '4')            # Graduate
            choose('kycResidenceType', '1')        # Owned
            choose('kycLoanPurpose', '5')          # Business Expansion
            fill('kycCibilScore', '760')
            choose('kycPreviousDefault', '0')      # No
            fill('kycMonthsAsCustomer', '48')
            fill('kycLatePayments', '0')
            fill('kycExistingLoans', '1')
            fill('kycExistingProducts', '3')
            choose('kycIsRural', '0')              # Urban

            # Step 3 — Financial Metrics
            fill('debtToEquity', '1.5')
            fill('interestCoverage', '3.5')
            fill('profitabilityMargin', '12')
            fill('liquidityRatio', '1.8')

            # Step 4a — AIRB Collateral & Loan
            choose('seniority', 'Senior Secured (Other)')
            choose('loanType', 'Term Loan Long')
        step('TC-03: Full form (KYC + Financial + AIRB) accepts valid input', tc03)

        # ── TC-04: ML PD calculation completes ──────────────────────────────
        def tc04():
            driver.find_element(By.ID, 'calculateBtn').click()
            wait.until(EC.visibility_of_element_located((By.ID, 'resultsSection')))
            pd_text = driver.find_element(By.ID, 'pdValue').text
            assert pd_text and pd_text not in ('--', '—', ''), \
                f'PD value is empty or placeholder: {pd_text!r}'
            btn = driver.find_element(By.ID, 'calculateBtn')
            assert btn.is_enabled(), 'Calculate button still disabled after completion'
        step('TC-04: ML PD calculation completes', tc04)

        # ── TC-05: Loan records to portfolio ────────────────────────────────
        def tc05():
            confirm_btn = driver.find_element(
                By.XPATH, "//button[contains(text(),'Confirm') and contains(text(),'Record')]")
            driver.execute_script('arguments[0].scrollIntoView(true)', confirm_btn)
            time.sleep(0.5)
            confirm_btn.click()
            time.sleep(1.5)
            wait.until(EC.presence_of_element_located((By.ID, 'portfolioSection')))
            rows = driver.find_elements(By.CSS_SELECTOR, '#loansTableBody tr')
            assert len(rows) >= 1, f'Expected at least 1 portfolio row, found {len(rows)}'
        step('TC-05: Loan records to portfolio', tc05)

        # ── TC-06: Portfolio summary shows non-zero values ───────────────────
        def tc06():
            loan_count = driver.find_element(By.ID, 'summaryLoanCount').text.strip()
            total_rwa  = driver.find_element(By.ID, 'summaryTotalRWA').text.strip()
            assert loan_count not in ('', '0', '—'), f'Loan count unexpected: {loan_count!r}'
            assert total_rwa  not in ('', '₹0', '0', '—'), f'Total RWA unexpected: {total_rwa!r}'
        step('TC-06: Portfolio summary updates correctly', tc06)

    except Exception as e:
        results.append({
            'name': 'Unexpected suite error',
            'passed': False,
            'error': traceback.format_exc(),
            'duration_seconds': None
        })
    finally:
        if driver:
            driver.quit()

    total  = len(results)
    passed = sum(1 for r in results if r['passed'])
    failed = total - passed

    return {
        'status': 'completed',
        'tests': results,
        'summary': {
            'total': total,
            'passed': passed,
            'failed': failed,
            'duration_seconds': round(time.time() - suite_start, 2)
        }
    }


if __name__ == '__main__':
    import json
    out = run_smoke_tests()
    print(json.dumps(out, indent=2))
