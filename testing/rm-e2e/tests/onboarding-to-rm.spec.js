// End-to-end test: complete onboarding → RM approval flow.
//
// Simulates the single-channel origination path:
//   Credit Risk calculator (data collection + risk assessment)
//     → "Refer to Relationship Manager" (creates RM case, opens cockpit in new tab)
//       → RM reviews + accepts (final decision)
//         → Underwriter dossier opens in third tab (optional verify)
//
// Scenario A — strong applicant (expect machine recommendation to approve, RM accepts)
// Scenario B — weak applicant  (RM rejects with a documented rationale)
//
// Cases are named "PWTEST ..." so global-teardown purges them automatically.

const { test, expect } = require('@playwright/test');

const RUN = String(Date.now()).slice(-6);
const name = (tag) => `PWTEST ${tag} ${RUN}`;

// ── Helpers ────────────────────────────────────────────────────────────────

/** Fill the onboarding form and run the risk assessment.
 *  Returns the page (still on the calculator) after results are shown. */
async function fillAndAssess(page, opts) {
  await page.goto('/borrower-info.html');

  // ── Borrower identity ──────────────────────────────────────────────────
  await page.locator('#borrowerId').fill(opts.borrowerId);
  await page.locator('#borrowerName').fill(opts.borrowerName);
  await page.locator('#exposureAmount').fill(String(opts.exposure));

  // ── Country (wait for dropdown to populate from /reference/api/countries)
  await page.locator('#country').waitFor({ state: 'attached' });
  await page.waitForFunction(() => {
    const sel = document.getElementById('country');
    return sel && sel.options.length > 1;
  }, { timeout: 15_000 });
  await page.locator('#country').selectOption({ value: opts.country });

  // ── Industry sector ────────────────────────────────────────────────────
  await page.locator('#sector').selectOption(opts.sector ?? 'Technology');

  // ── Onboarding & compliance ────────────────────────────────────────────
  await page.locator('#kycStatusField').selectOption(opts.kycStatus);
  await page.locator('#screeningField').selectOption(opts.screening);
  await page.locator('#proposedEmi').fill(String(opts.proposedEmi));
  await page.locator('#existingObligations').fill(String(opts.existingObl));

  // ── Borrower profile ───────────────────────────────────────────────────
  await page.locator('#kycAge').fill(String(opts.age));
  await page.locator('#kycEmploymentType').selectOption(String(opts.empType));
  await page.locator('#kycYearsEmployed').fill(String(opts.yearsEmp));
  await page.locator('#kycAnnualIncome').fill(String(opts.income));
  await page.locator('#kycFoir').fill(String(opts.foir));
  await page.locator('#kycNumDependents').fill(String(opts.dependents));
  await page.locator('#kycCityTier').selectOption(String(opts.cityTier));
  await page.locator('#kycEducation').selectOption(String(opts.education));
  await page.locator('#kycResidenceType').selectOption(String(opts.residenceType));

  // ── Bureau data ────────────────────────────────────────────────────────
  await page.locator('#kycCibilScore').fill(String(opts.cibil));
  await page.locator('#kycPreviousDefault').selectOption(String(opts.prevDefault));
  await page.locator('#kycLatePayments').fill(String(opts.latePayments));
  await page.locator('#kycExistingLoans').fill(String(opts.existingLoans));
  await page.locator('#kycExistingProducts').fill(String(opts.existingProducts));
  await page.locator('#kycMonthsAsCustomer').fill(String(opts.monthsAsCustomer));
  await page.locator('#kycLoanPurpose').selectOption(String(opts.loanPurpose));
  await page.locator('#kycIsRural').selectOption(String(opts.isRural ?? 0));

  // ── Financial ratios ───────────────────────────────────────────────────
  await page.locator('#debtToEquity').fill(String(opts.de));
  await page.locator('#interestCoverage').fill(String(opts.ic));
  await page.locator('#profitabilityMargin').fill(String(opts.pm));
  await page.locator('#liquidityRatio').fill(String(opts.lq));

  // ── AIRB parameters ────────────────────────────────────────────────────
  await page.locator('#seniority').selectOption(opts.seniority ?? 'Senior Unsecured');
  await page.locator('#loanType').selectOption(opts.loanType ?? 'Term Loan Short');
  await page.locator('#collateralValue').fill(String(opts.collateral ?? 0));

  // ── Calculate ─────────────────────────────────────────────────────────
  await page.locator('#calculateBtn').click();

  // Wait for the Risk Assessment Summary band to populate (ML call completes)
  await expect(page.locator('#resultsSection')).toBeVisible({ timeout: 30_000 });
  // The "Refer to RM" button appears once results are shown
  await expect(page.locator('#sendToRmBtn')).toBeVisible({ timeout: 15_000 });
}

/** Click "Refer to Relationship Manager", capture the new tab, wait for cockpit. */
async function referToRM(page) {
  // sendToRM() calls window.open('...', '_blank') — capture the popup tab
  const [rmPage] = await Promise.all([
    page.context().waitForEvent('page'),
    page.locator('#sendToRmBtn').click(),
  ]);
  await rmPage.waitForLoadState('domcontentloaded');
  // Cockpit loads the case — wait for the RM decision panel
  await expect(rmPage.getByText('Relationship Manager Decision')).toBeVisible({ timeout: 30_000 });
  return rmPage;
}

// ── Test data ──────────────────────────────────────────────────────────────

const STRONG = {
  borrowerId:       'PWTEST-STR-' + RUN,
  borrowerName:     name('strong applicant'),
  exposure:         2_500_000,
  country:          'IND',
  kycStatus:        'Verified',
  screening:        'clean',
  proposedEmi:      35_000,
  existingObl:      8_000,
  age:              38,
  empType:          2,    // Salaried-Private
  yearsEmp:         10,
  income:           2_400_000,
  foir:             0.28,
  dependents:       1,
  cityTier:         1,    // Tier-1
  education:        4,    // Graduate
  residenceType:    1,    // Owned
  cibil:            790,
  prevDefault:      0,
  latePayments:     0,
  existingLoans:    1,
  existingProducts: 3,
  monthsAsCustomer: 60,
  loanPurpose:      1,    // Home Purchase
  isRural:          0,    // Urban
  de:               0.9,
  ic:               7.5,
  pm:               16,
  lq:               2.2,
  collateral:       1_500_000,
  seniority:        'Senior Secured (Real Estate)',
  loanType:         'Term Loan Long',
};

const WEAK = {
  borrowerId:       'PWTEST-WEK-' + RUN,
  borrowerName:     name('weak applicant'),
  exposure:         1_200_000,
  country:          'IND',
  kycStatus:        'Pending',
  screening:        'sanctions',
  proposedEmi:      52_000,
  existingObl:      35_000,
  age:              29,
  empType:          7,    // Student
  yearsEmp:         1,
  income:           360_000,
  foir:             0.72,
  dependents:       3,
  cityTier:         3,    // Tier-3
  education:        2,    // 10th
  residenceType:    2,    // Rented
  cibil:            580,
  prevDefault:      1,
  latePayments:     5,
  existingLoans:    3,
  existingProducts: 1,
  monthsAsCustomer: 4,
  loanPurpose:      4,    // Personal Loan
  isRural:          1,    // Rural
  de:               4.8,
  ic:               1.1,
  pm:               -3,
  lq:               0.7,
  collateral:       0,
  seniority:        'Senior Unsecured',
  loanType:         'Working Capital',
};

// ── Tests ──────────────────────────────────────────────────────────────────

test.describe('Onboarding → RM decision flow', () => {

  test('Scenario A: strong applicant → RM accepts → final decision recorded', async ({ page }) => {
    // Step 1 — fill calculator and run assessment
    await fillAndAssess(page, STRONG);

    // The Risk Assessment Summary shows PD value and no verdict pill
    await expect(page.locator('#resultsSection')).toContainText('Risk Assessment Summary');
    const pdText = await page.locator('#pdValue').textContent();
    expect(pdText).toMatch(/\d+(\.\d+)?%/);   // e.g. "3.2%"

    // Step 2 — refer to RM (opens cockpit in new tab)
    const rmPage = await referToRM(page);

    // Step 3 — RM reviews the cockpit
    // The borrower name from the calculator should appear in the cockpit
    await expect(rmPage.getByText('strong applicant', { exact: false }).first()).toBeVisible();

    // Machine recommendation section is present (model-suggested advisory)
    await expect(rmPage.getByText('Machine Recommendation', { exact: false }).first()).toBeVisible();

    // Step 4 — RM accepts
    await rmPage.getByRole('button', { name: /Accept & finalise/ }).click();

    // Step 5 — verify final decision
    await expect(rmPage.getByText('Final Decision')).toBeVisible({ timeout: 15_000 });
    await expect(rmPage.locator('.badge', { hasText: 'DECISION FINAL' }).first()).toBeVisible();
    await expect(rmPage.getByText('Accepted the recommendation', { exact: false })).toBeVisible();
  });

  test('Scenario B: weak applicant → RM rejects with documented rationale → DECLINE recorded', async ({ page }) => {
    // Step 1 — fill calculator and run assessment
    await fillAndAssess(page, WEAK);

    await expect(page.locator('#resultsSection')).toContainText('Risk Assessment Summary');

    // Step 2 — refer to RM
    const rmPage = await referToRM(page);
    await expect(rmPage.getByText('weak applicant', { exact: false }).first()).toBeVisible();

    // Step 3 — RM clicks Reject
    await rmPage.getByRole('button', { name: /Reject application/ }).click();

    // Too-short rationale is rejected client-side
    await rmPage.locator('#ratText').fill('too short');
    await rmPage.getByRole('button', { name: /Confirm rejection/ }).click();
    await expect(rmPage.locator('#toast')).toContainText('at least 20 characters');

    // Step 4 — valid rationale finalises as DECLINE
    await rmPage.locator('#ratText').fill(
      'KYC pending and bureau shows prior default with 5 late payments. Application does not meet policy thresholds.'
    );
    await rmPage.getByRole('button', { name: /Confirm rejection/ }).click();

    await expect(rmPage.getByText('Final Decision')).toBeVisible({ timeout: 15_000 });
    await expect(rmPage.locator('.badge', { hasText: 'DECLINE' }).first()).toBeVisible();
  });

  test('Scenario C: strong applicant → RM accepts → PDF report generates', async ({ page }) => {
    // Reuse the strong profile but with a distinct borrower ID to avoid duplication
    const opts = { ...STRONG, borrowerId: 'PWTEST-PDF-' + RUN, borrowerName: name('pdf applicant') };
    await fillAndAssess(page, opts);

    const rmPage = await referToRM(page);
    await rmPage.getByRole('button', { name: /Accept & finalise/ }).click();
    await expect(rmPage.getByText('Final Decision')).toBeVisible({ timeout: 15_000 });

    // Generate PDF report
    const genBtn = rmPage.locator('#genReportBtn');
    await expect(genBtn).toBeVisible();
    await genBtn.click();

    const openLinks = rmPage.locator('#reportList a', { hasText: 'Open' });
    await expect(openLinks.first()).toBeVisible({ timeout: 60_000 });
    await expect(rmPage.locator('#reportList .badge', { hasText: 'latest' })).toBeVisible();

    // Verify the PDF is actually served
    const href = await openLinks.first().getAttribute('href');
    const resp = await rmPage.request.get(href);
    expect(resp.ok()).toBeTruthy();
    expect(resp.headers()['content-type']).toContain('application/pdf');

    // Underwriter report link is present (opens the rich dossier for this case)
    await expect(rmPage.locator('a', { hasText: 'Underwriter report' })).toBeVisible();
  });

  test('Scenario D: customer ID lookup autofills from existing bank record', async ({ page }) => {
    await page.goto('/borrower-info.html');

    // Type an existing customer ID from the seeded data
    const cidInput = page.locator('#borrowerId');
    await cidInput.fill('AXIS-SME-0001');

    // Trigger lookup (blur fires the lookup)
    await cidInput.press('Tab');
    // Give the async fetch a moment to complete
    await page.waitForTimeout(2000);

    // Green banner should appear with "Existing customer found"
    await expect(page.locator('#custLookupBanner')).toBeVisible({ timeout: 10_000 });
    await expect(page.locator('#custLookupBanner')).toContainText('Existing customer found');

    // Confirm autofill populates the CIBIL score field
    const confirmBtn = page.locator('#custLookupBanner button', { hasText: /Autofill/ });
    await expect(confirmBtn).toBeVisible();
    await confirmBtn.click();

    // CIBIL field should now be populated (> 0)
    const cibil = await page.locator('#kycCibilScore').inputValue();
    expect(parseInt(cibil, 10)).toBeGreaterThan(0);

    // Country field should also be set
    const country = await page.locator('#country').inputValue();
    expect(country).toBeTruthy();
  });
});
