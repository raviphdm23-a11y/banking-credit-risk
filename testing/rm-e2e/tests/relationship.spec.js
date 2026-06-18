// End-to-end tests for the Relationship Management & Decision Support cockpit.
// Covers the simplified two-option RM workflow + PDF case reports + insights.
//
// Cases are created via the REST API (POST /relationship/api/cases) rather than
// through the UI intake form — the RM no longer has its own form (single-channel
// origination: all data collection happens on the Credit Risk calculator page).
// These tests are purely about cockpit behaviour once a case exists.
//
// Every case created here is named "PWTEST ..." so global-teardown can purge it.
const { test, expect } = require('@playwright/test');

const BASE = 'http://127.0.0.1:5000';
const RUN  = String(Date.now()).slice(-6);
const name = (tag) => `PWTEST ${tag} ${RUN}`;

// ── Helpers ────────────────────────────────────────────────────────────────

/** Create an RM case via the API and open its cockpit page.
 *  Returns { page, caseId }. */
async function openCockpit(page, opts) {
  const payload = {
    customer_name: opts.name,
    product:       opts.product  ?? 'Term Loan',
    customer_id:   opts.customerId ?? null,
    application: {
      borrower_id:            opts.name.replace(/\s+/g, '-'),
      borrower_name:          opts.name,
      exposure_amount:        opts.exposure        ?? 2_000_000,
      de_ratio:               opts.de              ?? 1.0,
      interest_coverage:      opts.ic              ?? 6.0,
      profitability:          opts.pm              ?? 14.0,
      liquidity_ratio:        opts.lq              ?? 2.0,
      age:                    opts.age             ?? 35,
      annual_income:          opts.income          ?? 1_200_000,
      foir:                   opts.foir            ?? 0.30,
      cibil_score:            opts.cibil           ?? 760,
      num_late_payments_past_12m: opts.late        ?? 0,
      previous_default_flag:  opts.prevDefault     ?? 0,
      existing_loans_count:   opts.existingLoans   ?? 1,
      employment_type_enc:    opts.empType         ?? 2,
      education_enc:          opts.education       ?? 4,
      city_tier_enc:          opts.cityTier        ?? 1,
      residence_type_enc:     opts.residenceType   ?? 1,
      loan_purpose_enc:       opts.loanPurpose     ?? 1,
      num_dependents:         opts.dependents      ?? 1,
      months_as_customer:     opts.monthsAsCustomer ?? 24,
      num_existing_products:  opts.existingProducts ?? 2,
      years_employed:         opts.yearsEmp        ?? 8,
      is_rural:               opts.isRural         ?? 0,
      num_late_payments:      opts.late            ?? 0,
      kyc_status:             opts.kycStatus       ?? 'Verified',
      pep_flag:               opts.pepFlag         ?? false,
      sanctions_hit:          opts.sanctionsHit    ?? false,
      proposed_emi:           opts.proposedEmi     ?? 30_000,
      existing_monthly_obligations: opts.existingObl ?? 10_000,
      country_code:           opts.countryCode     ?? 'IND',
    },
  };

  const resp = await page.request.post(`${BASE}/relationship/api/cases`, {
    data: payload,
    headers: { 'Content-Type': 'application/json' },
  });
  expect(resp.ok()).toBeTruthy();
  const body = await resp.json();
  const caseId = body.case_id;
  expect(caseId).toBeTruthy();

  await page.goto(`/relationship/?case=${caseId}`);
  await expect(page.getByText('Relationship Manager Decision')).toBeVisible({ timeout: 20_000 });
  return { page, caseId };
}

// ── Tests ──────────────────────────────────────────────────────────────────

test.describe('Relationship Management — decision workflow', () => {

  test('Scenario 1: a strong applicant can be accepted and finalised', async ({ page }) => {
    await openCockpit(page, {
      name: name('accept'), cibil: 800, late: 0, prevDefault: 0,
      de: 0.8, ic: 8, pm: 18, lq: 2.5,
    });

    await page.getByRole('button', { name: /Accept & finalise/ }).click();

    await expect(page.getByText('Final Decision')).toBeVisible({ timeout: 15_000 });
    await expect(page.locator('.badge', { hasText: 'DECISION FINAL' }).first()).toBeVisible();
    await expect(page.getByText('Accepted the recommendation')).toBeVisible();
  });

  test('Scenario 2: rejecting requires a >= 20-character rationale', async ({ page }) => {
    await openCockpit(page, {
      name: name('reject'), cibil: 600, late: 4, prevDefault: 1,
      de: 3.0, ic: 1.5, pm: 2, lq: 0.9,
    });

    await page.getByRole('button', { name: /Reject application/ }).click();

    // Too-short rationale is blocked client-side.
    await page.locator('#ratText').fill('too short');
    await page.getByRole('button', { name: /Confirm rejection/ }).click();
    await expect(page.locator('#toast')).toContainText('at least 20 characters');
    await expect(page.getByText('Relationship Manager Decision')).toBeVisible();

    // A proper rationale finalises as DECLINE.
    await page.locator('#ratText').fill('Applicant withdrew after review and the profile breaches policy thresholds.');
    await page.getByRole('button', { name: /Confirm rejection/ }).click();
    await expect(page.getByText('Final Decision')).toBeVisible({ timeout: 15_000 });
    await expect(page.locator('.badge', { hasText: 'DECLINE' }).first()).toBeVisible();
  });

  test('Scenario 3: PDF reports generate and prior versions are retained', async ({ page }) => {
    await openCockpit(page, { name: name('report'), cibil: 760, late: 0, prevDefault: 0 });

    const genBtn   = page.locator('#genReportBtn');
    const openLinks = page.locator('#reportList a', { hasText: 'Open' });

    // First generation → one openable version, flagged "latest".
    await genBtn.click();
    await expect(openLinks.first()).toBeVisible({ timeout: 60_000 });
    await expect(page.locator('#reportList .badge', { hasText: 'latest' })).toBeVisible();

    // The link actually serves a PDF.
    const href = await openLinks.first().getAttribute('href');
    const resp = await page.request.get(href);
    expect(resp.ok()).toBeTruthy();
    expect(resp.headers()['content-type']).toContain('application/pdf');

    // Regenerating keeps history → two versions now.
    await genBtn.click();
    await expect(openLinks).toHaveCount(2, { timeout: 60_000 });
  });

  test('Scenario 4: governance insights reflect a finalised decision', async ({ page }) => {
    const { page: p } = await openCockpit(page, {
      name: name('insights'), cibil: 780, late: 0, prevDefault: 0,
      de: 0.9, ic: 7, pm: 15, lq: 2.0,
    });

    await p.getByRole('button', { name: /Accept & finalise/ }).click();
    await expect(p.getByText('Final Decision')).toBeVisible({ timeout: 15_000 });

    await p.getByRole('button', { name: /Governance Insights/ }).click();
    await expect(p.getByText('Governance & Learning Insights')).toBeVisible();

    const kpiValue = p.locator('.kpi', { hasText: 'Final decisions' }).locator('.v');
    await expect(kpiValue).toBeVisible();
    const count = parseInt((await kpiValue.textContent()).trim(), 10);
    expect(count).toBeGreaterThanOrEqual(1);
  });
});
