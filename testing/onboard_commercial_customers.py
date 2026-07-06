"""
onboard_commercial_customers.py
────────────────────────────────
Playwright script that visibly onboards one new CORPORATE (commercial)
customer at EACH of the 9 banks, driving the platform's real UI end-to-end
exactly as a human would:

    1. Credit Risk Analysis  — fill borrower-info.html, calculate PD/LGD/RWA
    2. Relationship Management / Decision Support — "Refer to Relationship
       Manager" opens the case in a new tab with the Machine Recommendation
    3. Approval — RM clicks "Accept & finalise", which finalises the case as
       APPROVE and books a real loan to the originating bank's ledger
       (backend/loan_booking.py, via rm_case_store._finalise)

Runs headed (visible browser window) with slow_mo so each step can be
watched, not just asserted. Requires Flask already running on
http://127.0.0.1:5000.

Run:  python testing/onboard_commercial_customers.py
"""
import time
from datetime import datetime
from playwright.sync_api import sync_playwright

BASE_URL = "http://127.0.0.1:5000"

# bank_id -> (bank_name, country_code) - country_code drives the jurisdiction
# dropdown so each commercial customer is onboarded in its bank's home market.
BANKS = [
    ("BANK001", "HDFC Bank Limited", "IND"),
    ("BANK002", "ICICI Bank Limited", "IND"),
    ("BANK003", "JPMorgan Chase Bank N.A.", "USA"),
    ("BANK004", "Barclays Bank PLC", "GBR"),
    ("BANK005", "DBS Bank Ltd", "SGP"),
    ("BANK006", "Emirates NBD PJSC", "ARE"),
    ("BANK007", "Bank of Baroda", "IND"),
    ("BANK008", "Commonwealth Bank of Australia", "AUS"),
    ("BANK009", "Punjab National Bank", "IND"),
]

RUN_TAG = datetime.now().strftime("%H%M%S")
SLOW_MO_MS = 250  # milliseconds between each Playwright action - visible pace
PAUSE_S = 0.6     # extra pause at key checkpoints so a human can watch


def fill_application(page, bank_id, bank_name, country_code, idx):
    """Step 1: Credit Risk Analysis - fill the full origination form."""
    borrower_id = f"CORP-{RUN_TAG}-{bank_id}"
    borrower_name = f"{bank_name.split()[0]} Commercial Client {idx}"

    page.goto(f"{BASE_URL}/borrower-info.html")
    # <option> elements are never "visible" in Playwright's layout sense
    # (only their parent <select> is) - wait for them to be attached instead,
    # since both dropdowns are populated asynchronously from the API on load.
    page.wait_for_selector("#bankSelect option[value='BANK001']", state="attached", timeout=15000)
    page.wait_for_selector("#exposureClass option[value='CORPORATE']", state="attached", timeout=15000)

    # ── Step 1: Basic Information ──────────────────────────────────────────
    page.fill("#borrowerId", borrower_id)
    page.fill("#borrowerName", borrower_name)
    page.fill("#exposureAmount", "20000000")   # ₹2 Cr commercial exposure
    page.select_option("#country", country_code)
    page.select_option("#sector", "Manufacturing")
    page.check("#modeAIRB")  # AIRB methodology (default, but explicit)

    # ── Step 2: Borrower Profile (KYC) ─────────────────────────────────────
    page.fill("#kycAge", "45")
    page.select_option("#kycEmploymentType", "4")   # Business Owner
    page.fill("#kycYearsEmployed", "15")
    page.fill("#kycAnnualIncome", "25000000")
    page.fill("#kycFoir", "0.25")
    page.fill("#kycNumDependents", "2")
    page.select_option("#kycCityTier", "1")
    page.select_option("#kycEducation", "5")         # Post Graduate
    page.select_option("#kycResidenceType", "1")     # Owned
    page.select_option("#kycLoanPurpose", "5")        # Business Expansion
    page.fill("#kycCibilScore", "800")
    page.select_option("#kycPreviousDefault", "0")    # No
    page.fill("#kycMonthsAsCustomer", "36")
    page.fill("#kycLatePayments", "0")
    page.fill("#kycExistingLoans", "1")
    page.fill("#kycExistingProducts", "3")
    page.select_option("#kycIsRural", "0")            # Urban

    # ── Step 3: Financial Metrics (healthy commercial borrower) ────────────
    page.fill("#debtToEquity", "0.5")
    page.fill("#interestCoverage", "5.0")
    page.fill("#profitabilityMargin", "18")
    page.fill("#liquidityRatio", "1.8")

    # ── Step 4a: Collateral, Bank, Exposure Class, Loan Type ───────────────
    page.select_option("#bankSelect", bank_id)
    page.select_option("#exposureClass", "CORPORATE")
    page.select_option("#loanType", "Term Loan Short")

    return borrower_id, borrower_name


def submit_for_assessment(page):
    """Step 1 continued: run the Credit Risk calculation (PD/LGD/RWA/EL)."""
    page.click("#calculateBtn")
    page.wait_for_selector("#resultsSection.active", timeout=20000)
    time.sleep(PAUSE_S)
    # Exec band + "Refer to Relationship Manager" button render after the
    # /api/generate-report call resolves in the background.
    page.wait_for_selector("#sendToRmBtn", timeout=20000)
    time.sleep(PAUSE_S)


def refer_to_rm(page, context):
    """Step 2: Refer to Relationship Manager - opens the case in a new tab."""
    with context.expect_page() as new_page_info:
        page.click("#sendToRmBtn")
    rm_page = new_page_info.value
    rm_page.wait_for_load_state("domcontentloaded")
    return rm_page


def approve_case(rm_page):
    """Step 2 (Decision Support) + Step 3 (Approval): wait for the Machine
    Recommendation to render, then RM clicks Accept & finalise."""
    rm_page.wait_for_selector("text=Machine Recommendation (M)", timeout=20000)
    time.sleep(PAUSE_S)
    rm_page.wait_for_selector("button:has-text('Accept & finalise')", timeout=20000)
    time.sleep(PAUSE_S)
    rm_page.click("button:has-text('Accept & finalise')")
    rm_page.wait_for_selector("text=Final Decision", timeout=20000)
    time.sleep(PAUSE_S)
    badge_text = rm_page.inner_text(".card:has-text('Final Decision') .badge")
    return badge_text.strip()


def main():
    print(f"Onboarding {len(BANKS)} commercial customers (run tag: {RUN_TAG})\n")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=SLOW_MO_MS)
        context = browser.new_context()
        page = context.new_page()

        results = []
        for idx, (bank_id, bank_name, country_code) in enumerate(BANKS, start=1):
            print(f"[{idx}/{len(BANKS)}] {bank_name} ({bank_id}) ...")
            borrower_id, borrower_name = fill_application(page, bank_id, bank_name, country_code, idx)
            print(f"    Filled application for '{borrower_name}' ({borrower_id})")

            submit_for_assessment(page)
            print("    Credit risk assessment complete (PD/LGD/RWA calculated)")

            rm_page = refer_to_rm(page, context)
            print("    Referred to Relationship Manager - decision-support case opened")

            final_decision = approve_case(rm_page)
            print(f"    RM decision: {final_decision}\n")
            results.append((bank_id, bank_name, borrower_id, final_decision))

            rm_page.close()
            time.sleep(PAUSE_S)

        browser.close()

    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    for bank_id, bank_name, borrower_id, decision in results:
        print(f"  {bank_id:<10}{bank_name:<32}{borrower_id:<24}{decision}")


if __name__ == "__main__":
    main()
