"""
Selenium test for the Admin Dashboard — Smoke Tests panel.
Verifies that an admin user can:
  1. Open admin.html and authenticate
  2. Navigate to the Smoke Tests panel
  3. Trigger a smoke test run
  4. Wait for results to appear
  5. Confirm all consumer-side tests passed
"""

import sys
import os
import time

if sys.platform == 'win32':
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

BASE_URL    = 'http://127.0.0.1:5000'
ADMIN_PASS  = '1234'
MAX_WAIT    = 15    # seconds for normal UI interactions
SMOKE_WAIT  = 120   # seconds for the smoke test run to finish


def run():
    print()
    print('=' * 70)
    print('ADMIN MODULE — SMOKE TEST TRIGGER (Selenium)')
    print('=' * 70)

    opts = Options()
    opts.add_argument('--disable-blink-features=AutomationControlled')
    opts.add_experimental_option('excludeSwitches', ['enable-automation'])
    opts.add_experimental_option('useAutomationExtension', False)

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=opts
    )
    wait  = WebDriverWait(driver, MAX_WAIT)
    smoke = WebDriverWait(driver, SMOKE_WAIT)

    passed = 0
    failed = 0

    def ok(msg):
        nonlocal passed
        passed += 1
        print(f'  [PASS] {msg}')

    def fail(msg, err=''):
        nonlocal failed
        failed += 1
        detail = f' — {str(err)[:120]}' if err else ''
        print(f'  [FAIL] {msg}{detail}')

    def step(label, fn):
        try:
            fn()
            ok(label)
            return True
        except Exception as e:
            fail(label, e)
            return False

    try:
        # ── STEP 1: Open admin page ──────────────────────────────────────────
        print('\n[1] Opening admin page...')
        def _open():
            driver.get(f'{BASE_URL}/admin.html')
            wait.until(EC.presence_of_element_located((By.ID, 'authOverlay')))
            assert driver.find_element(By.ID, 'authOverlay').is_displayed(), \
                'Auth overlay not visible'
        step('Admin page loads and shows password prompt', _open)

        # ── STEP 2: Authenticate ─────────────────────────────────────────────
        print('\n[2] Authenticating...')
        def _auth():
            pwd_input = driver.find_element(By.ID, 'authInput')
            pwd_input.send_keys(ADMIN_PASS)
            # No fixed ID on the Sign In button — locate by onclick attribute
            driver.find_element(
                By.XPATH, "//button[@onclick='checkPassword()']").click()
            wait.until(EC.invisibility_of_element_located((By.ID, 'authOverlay')))
            wait.until(EC.visibility_of_element_located((By.ID, 'app')))
        step('Password accepted, dashboard visible', _auth)

        # ── STEP 3: Navigate to Smoke Tests panel ────────────────────────────
        print('\n[3] Navigating to Smoke Tests panel...')
        def _nav():
            smoke_tab = wait.until(EC.element_to_be_clickable(
                (By.XPATH, "//nav/button[contains(text(),'Smoke Tests')]")))
            smoke_tab.click()
            wait.until(EC.visibility_of_element_located((By.ID, 'panel-smoketests')))
            run_btn = driver.find_element(By.ID, 'smokeRunBtn')
            assert run_btn.is_displayed(), 'Run Smoke Tests button not visible'
            assert run_btn.is_enabled(),   'Run Smoke Tests button is disabled'
        step('Smoke Tests panel opens with Run button enabled', _nav)

        # ── STEP 4: Click Run Smoke Tests ────────────────────────────────────
        print('\n[4] Clicking Run Smoke Tests...')
        def _click():
            # Hide any previous result so we can detect a fresh completion
            driver.execute_script(
                "document.getElementById('smokeResults').style.display='none';"
                "document.getElementById('smokeStatus').textContent='';"
            )
            driver.find_element(By.ID, 'smokeRunBtn').click()
            # Wait until button becomes disabled (running state)
            WebDriverWait(driver, 10).until(
                lambda d: not d.find_element(By.ID, 'smokeRunBtn').is_enabled()
                          or '⏳' in d.find_element(By.ID, 'smokeRunBtn').text
            )
        step('Run button clicked and enters running state', _click)

        # ── STEP 5: Wait for results table to appear ─────────────────────────
        print(f'\n[5] Waiting for smoke test results (up to {SMOKE_WAIT}s)...')
        def _wait_results():
            # Wait for results panel to become visible again (fresh run)
            smoke.until(EC.visibility_of_element_located((By.ID, 'smokeResults')))
            # Button must be re-enabled once done
            smoke.until(EC.element_to_be_clickable((By.ID, 'smokeRunBtn')))
        step('Results panel appeared and Run button re-enabled', _wait_results)

        # ── STEP 6: Check summary KPIs ───────────────────────────────────────
        print('\n[6] Checking summary KPIs...')
        def _kpis():
            total    = driver.find_element(By.ID, 'smoke-total').text.strip()
            passed_n = driver.find_element(By.ID, 'smoke-passed').text.strip()
            failed_n = driver.find_element(By.ID, 'smoke-failed').text.strip()
            duration = driver.find_element(By.ID, 'smoke-duration').text.strip()
            print(f'       Total={total}  Passed={passed_n}  Failed={failed_n}  Duration={duration}')
            assert total    not in ('', '—', '0'), f'Total still shows {total!r}'
            assert passed_n not in ('', '—'),      f'Passed still shows {passed_n!r}'
            assert failed_n == '0',                f'Expected 0 failures, got {failed_n!r}'
        step('Summary KPIs show non-zero total and zero failures', _kpis)

        # ── STEP 7: Verify per-test result rows ──────────────────────────────
        print('\n[7] Verifying per-test result rows...')
        def _rows():
            rows = driver.find_elements(By.CSS_SELECTOR, '#smokeTableBody tr')
            assert len(rows) > 0, 'No result rows in table'
            all_pass = True
            for row in rows:
                cells = row.find_elements(By.TAG_NAME, 'td')
                if len(cells) < 3:
                    continue
                name   = cells[1].text.strip()
                result = cells[2].text.strip()
                error  = cells[4].text.strip() if len(cells) > 4 else ''
                symbol = 'v' if result == 'PASS' else 'x'
                print(f'       [{symbol}] {name}: {result}' + (f' | {error[:60]}' if error and error != '—' else ''))
                if result != 'PASS':
                    all_pass = False
            assert all_pass, 'One or more consumer-side tests failed'
        step('All consumer-side test rows show PASS', _rows)

        # ── STEP 8: Status message confirms all passed ────────────────────────
        print('\n[8] Checking status message...')
        def _status_msg():
            status_el = driver.find_element(By.ID, 'smokeStatus')
            msg = status_el.text.strip()
            print(f'       Status: {msg}')
            assert 'passed' in msg.lower() or 'pass' in msg.lower(), \
                f'Status message does not confirm passing: {msg!r}'
        step('Status message confirms all tests passed', _status_msg)

    except Exception as e:
        fail('Unexpected suite error', e)

    finally:
        driver.quit()

        print()
        print('=' * 70)
        print('RESULTS')
        print('=' * 70)
        total = passed + failed
        print(f'  Passed : {passed}/{total}')
        print(f'  Failed : {failed}/{total}')
        if failed == 0:
            print('\n  [SUCCESS] Admin smoke test trigger works correctly.')
        else:
            print(f'\n  [WARNING] {failed} step(s) failed — review output above.')
        print('=' * 70)

    return failed == 0


if __name__ == '__main__':
    success = run()
    sys.exit(0 if success else 1)
