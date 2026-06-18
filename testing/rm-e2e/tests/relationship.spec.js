// End-to-end tests for the Relationship Management & Decision Support cockpit.
//
// Every test goes through the full single-channel origination path:
//   Credit Risk calculator (data collection + risk assessment)
//     → "Refer to Relationship Manager" (creates RM case, opens cockpit in new tab)
//       → RM acts in the cockpit
//
// This matches the real user journey: data collection happens ONLY on the
// Credit Risk calculator; the RM cockpit has no intake form of its own.
//
// Cases are named "PWTEST ..." so global-teardown can purge them automatically.

const { test, expect } = require('@playwright/test');

const RUN  = String(Date.now()).slice(-6);
const name = (tag) => `PWTEST ${tag} ${RUN}`;

// ── Helpers (same flow as onboarding-to-rm.spec.js) ───────────────────────

async function fillAndAssess(page, opts) {
  await page.goto('/borrower-info.html');

  await page.locator('#borrowerId').fill(opts.borrowerId);
  await page.locator('#borrowerName').fill(opts.borrowerName);
  await page.locator('#exposureAmount').fill(String(opts.exposure));

  await page.locator('#country').waitFor({ state: 'attached' });
  await page.waitForFunction(() => {
    const sel = document.getElementById('country');
    return sel && sel.options.length > 1;
  }, { timeout: 15_000 });
  await page.locator('#country').selectOption({ value: opts.country });

  await page.locator('#sector').selectOption(opts.sector ?? 'Technology');

  await page.locator('#kycStatusField').selectOption(opts.kycStatus);
  await page.locator('#screeningField').selectOption(opts.screening);
  await page.locator('#proposedEmi').fill(String(opts.proposedEmi));
  await page.locator('#existingObligations').fill(String(opts.existingObl));

  await page.locator('#kycAge').fill(String(opts.age));
  await page.locator('#kycEmploymentType').selectOption(String(opts.empType));
  await page.locator('#kycYearsEmployed').fill(String(opts.yearsEmp));
  await page.locator('#kycAnnualIncome').fill(String(opts.income));
  await page.locator('#kycFoir').fill(String(opts.foir));
  await page.locator('#kycNumDependents').fill(String(opts.dependents));
  await page.locator('#kycCityTier').selectOption(String(opts.cityTier));
  await page.locator('#kycEducation').selectOption(String(opts.education));
  await page.locator('#kycResidenceType').selectOption(String(opts.residenceType));

  await page.locator('#kycCibilScore').fill(String(opts.cibil));
  await page.locator('#kycPreviousDefault').selectOption(String(opts.prevDefault));
  await page.locator('#kycLatePayments').fill(String(opts.latePayments));
  await page.locator('#kycExistingLoans').fill(String(opts.existingLoans));
  await page.locator('#kycExistingProducts').fill(String(opts.existingProducts));
  await page.locator('#kycMonthsAsCustomer').fill(String(opts.monthsAsCustomer));
  await page.locator('#kycLoanPurpose').selectOption(String(opts.loanPurpose));
  await page.locator('#kycIsRural').selectOption(String(opts.isRural ?? 0));

  await page.locator('#debtToEquity').fill(String(opts.de));
  await page.locator('#interestCoverage').fill(String(opts.ic));
  await page.locator('#profitabilityMargin').fill(String(opts.pm));
  await page.locator('#liquidityRatio').fill(String(opts.lq));

  await page.locator('#seniority').selectOption(opts.seniority ?? 'Senior Unsecured');
  await page.locator('#loanType').selectOption(opts.loanType ?? 'Term Loan Short');
  await page.locator('#collateralValue').fill(String(opts.collateral ?? 0));

  await page.locator('#calculateBtn').click();

  await expect(page.locator('#resultsSection')).toBeVisible({ timeout: 30_000 });
  await expect(page.locator('#sendToRmBtn')).toBeVisible({ timeout: 15_000 });
}

async function referToRM(page) {
  const [rmPage] = await Promise.all([
    page.context().waitForEvent('page'),
    page.locator('#sendToRmBtn').click(),
  ]);
  await rmPage.waitForLoadState('domcontentloaded');
  await expect(rmPage.getByText('Relationship Manager Decision')).toBeVisible({ timeout: 30_000 });
  return rmPage;
}

// ── Test data ──────────────────────────────────────────────────────────────

const STRONG = (tag) => ({
  borrowerId:       `PWTEST-REL-STR-${tag}-${RUN}`,
  borrowerName:     name(`rel-strong-${tag}`),
  exposure:         2_500_000,
  country:          'IND',
  kycStatus:        'Verified',
  screening:        'clean',
  proposedEmi:      35_000,
  existingObl:      8_000,
  age:              38,
  empType:          2,
  yearsEmp:         10,
  income:           2_400_000,
  foir:             0.28,
  dependents:       1,
  cityTier:         1,
  education:        4,
  residenceType:    1,
  cibil:            790,
  prevDefault:      0,
  latePayments:     0,
  existingLoans:    1,
  existingProducts: 3,
  monthsAsCustomer: 60,
  loanPurpose:      1,
  isRural:          0,
  de:               0.9,
  ic:               7.5,
  pm:               16,
  lq:               2.2,
  collateral:       1_500_000,
  seniority:        'Senior Secured (Real Estate)',
  loanType:         'Term Loan Long',
});

const WEAK = (tag) => ({
  borrowerId:       `PWTEST-REL-WEK-${tag}-${RUN}`,
  borrowerName:     name(`rel-weak-${tag}`),
  exposure:         1_200_000,
  country:          'IND',
  kycStatus:        'Pending',
  screening:        'sanctions',
  proposedEmi:      52_000,
  existingObl:      35_000,
  age:              29,
  empType:          7,
  yearsEmp:         1,
  income:           360_000,
  foir:             0.72,
  dependents:       3,
  cityTier:         3,
  education:        2,
  residenceType:    2,
  cibil:            580,
  prevDefault:      1,
  latePayments:     5,
  existingLoans:    3,
  existingProducts: 1,
  monthsAsCustomer: 4,
  loanPurpose:      4,
  isRural:          1,
  de:               4.8,
  ic:               1.1,
  pm:               -3,
  lq:               0.7,
  collateral:       0,
  seniority:        'Senior Unsecured',
  loanType:         'Working Capital',
});

// ── Tests ──────────────────────────────────────────────────────────────────

test.describe('Relationship Management — decision workflow', () => {

  test('Scenario 1: a strong applicant can be accepted and finalised', async ({ page }) => {
    await fillAndAssess(page, STRONG('s1'));
    const rmPage = await referToRM(page);

    await rmPage.getByRole('button', { name: /Accept & finalise/ }).click();

    await expect(rmPage.getByText('Final Decision')).toBeVisible({ timeout: 15_000 });
    await expect(rmPage.locator('.badge', { hasText: 'DECISION FINAL' }).first()).toBeVisible();
    await expect(rmPage.getByText('Accepted the recommendation')).toBeVisible();
  });

  test('Scenario 2: rejecting requires a >= 20-character rationale', async ({ page }) => {
    await fillAndAssess(page, WEAK('s2'));
    const rmPage = await referToRM(page);

    await rmPage.getByRole('button', { name: /Reject application/ }).click();

    // Too-short rationale is blocked client-side.
    await rmPage.locator('#ratText').fill('too short');
    await rmPage.getByRole('button', { name: /Confirm rejection/ }).click();
    await expect(rmPage.locator('#toast')).toContainText('at least 20 characters');
    await expect(rmPage.getByText('Relationship Manager Decision')).toBeVisible();

    // A proper rationale finalises as DECLINE.
    await rmPage.locator('#ratText').fill('Applicant withdrew after review and the profile breaches policy thresholds.');
    await rmPage.getByRole('button', { name: /Confirm rejection/ }).click();
    await expect(rmPage.getByText('Final Decision')).toBeVisible({ timeout: 15_000 });
    await expect(rmPage.locator('.badge', { hasText: 'DECLINE' }).first()).toBeVisible();
  });

  test('Scenario 3: PDF reports generate and prior versions are retained', async ({ page }) => {
    await fillAndAssess(page, STRONG('s3'));
    const rmPage = await referToRM(page);

    // Accept first so the PDF includes the final decision
    await rmPage.getByRole('button', { name: /Accept & finalise/ }).click();
    await expect(rmPage.getByText('Final Decision')).toBeVisible({ timeout: 15_000 });

    const genBtn    = rmPage.locator('#genReportBtn');
    const openLinks = rmPage.locator('#reportList a', { hasText: 'Open' });

    // First generation → one openable version, flagged "latest".
    await genBtn.click();
    await expect(openLinks.first()).toBeVisible({ timeout: 60_000 });
    await expect(rmPage.locator('#reportList .badge', { hasText: 'latest' })).toBeVisible();

    // The link actually serves a PDF.
    const href = await openLinks.first().getAttribute('href');
    const resp = await rmPage.request.get(href);
    expect(resp.ok()).toBeTruthy();
    expect(resp.headers()['content-type']).toContain('application/pdf');

    // Regenerating keeps history → two versions now.
    await genBtn.click();
    await expect(openLinks).toHaveCount(2, { timeout: 60_000 });
  });

  test('Scenario 4: governance insights reflect a finalised decision', async ({ page }) => {
    await fillAndAssess(page, STRONG('s4'));
    const rmPage = await referToRM(page);

    await rmPage.getByRole('button', { name: /Accept & finalise/ }).click();
    await expect(rmPage.getByText('Final Decision')).toBeVisible({ timeout: 15_000 });

    await rmPage.getByRole('button', { name: /Governance Insights/ }).click();
    await expect(rmPage.getByText('Governance & Learning Insights')).toBeVisible();

    const kpiValue = rmPage.locator('.kpi', { hasText: 'Final decisions' }).locator('.v');
    await expect(kpiValue).toBeVisible();
    const count = parseInt((await kpiValue.textContent()).trim(), 10);
    expect(count).toBeGreaterThanOrEqual(1);
  });

});
