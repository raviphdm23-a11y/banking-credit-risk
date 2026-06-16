// End-to-end tests for the Relationship Management & Decision Support cockpit.
// Covers the simplified two-option RM workflow + PDF case reports + insights.
//
// Every case created here is named "PWTEST ..." so global-teardown can purge it.
const { test, expect } = require('@playwright/test');

const RUN = String(Date.now()).slice(-6);
const name = (tag) => `PWTEST ${tag} ${RUN}`;

/**
 * Open the cockpit, start a new assessment, fill the relevant fields and submit.
 * Resolves once the case cockpit (RM decision panel) is on screen.
 */
async function newAssessment(page, opts) {
  await page.goto('/relationship/');
  await page.getByRole('button', { name: '+ New Assessment' }).click();
  await page.locator('#f_name').fill(opts.name);

  const set = async (sel, val) => {
    if (val !== undefined && val !== null) await page.locator(sel).fill(String(val));
  };
  await set('#f_cibil', opts.cibil);
  await set('#f_late', opts.late);
  if (opts.prevdef !== undefined) await page.locator('#f_prevdef').selectOption(String(opts.prevdef));
  await set('#f_de', opts.de);
  await set('#f_ic', opts.ic);
  await set('#f_pm', opts.pm);
  await set('#f_lq', opts.lq);

  await page.locator('#submitBtn').click();
  // The cockpit's RM decision panel proves the interim assessment was created.
  await expect(page.getByText('Relationship Manager Decision')).toBeVisible();
}

test.describe('Relationship Management — decision workflow', () => {

  test('Scenario 1: a strong applicant can be accepted and finalised', async ({ page }) => {
    await newAssessment(page, {
      name: name('accept'), cibil: 800, late: 0, prevdef: 0,
      de: 0.8, ic: 8, pm: 18, lq: 2.5,
    });

    await page.getByRole('button', { name: /Accept & finalise/ }).click();

    // The case is finalised: the "Final Decision" section + a DECISION FINAL state badge appear.
    await expect(page.getByText('Final Decision')).toBeVisible();
    await expect(page.locator('.badge', { hasText: 'DECISION FINAL' }).first()).toBeVisible();
    // Accepting the machine line is recorded as alignment (not an override).
    await expect(page.getByText('Accepted the recommendation')).toBeVisible();
  });

  test('Scenario 2: rejecting requires a >= 20-character rationale', async ({ page }) => {
    await newAssessment(page, {
      name: name('reject'), cibil: 600, late: 4, prevdef: 1,
      de: 3.0, ic: 1.5, pm: 2, lq: 0.9,
    });

    await page.getByRole('button', { name: /Reject application/ }).click();

    // Too-short rationale is blocked client-side with an error toast.
    await page.locator('#ratText').fill('too short');
    await page.getByRole('button', { name: /Confirm rejection/ }).click();
    await expect(page.locator('#toast')).toContainText('at least 20 characters');
    // Still not finalised — the RM decision panel is still showing.
    await expect(page.getByText('Relationship Manager Decision')).toBeVisible();

    // A proper rationale finalises the case as a DECLINE.
    await page.locator('#ratText').fill('Applicant withdrew after review and the profile breaches policy thresholds.');
    await page.getByRole('button', { name: /Confirm rejection/ }).click();
    await expect(page.getByText('Final Decision')).toBeVisible();
    await expect(page.locator('.badge', { hasText: 'DECLINE' }).first()).toBeVisible();
  });

  test('Scenario 3: PDF reports generate and prior versions are retained', async ({ page }) => {
    await newAssessment(page, { name: name('report'), cibil: 760, late: 0, prevdef: 0 });

    const genBtn = page.locator('#genReportBtn');
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
    await newAssessment(page, {
      name: name('insights'), cibil: 780, late: 0, prevdef: 0,
      de: 0.9, ic: 7, pm: 15, lq: 2.0,
    });
    await page.getByRole('button', { name: /Accept & finalise/ }).click();
    await expect(page.getByText('Final Decision')).toBeVisible();

    await page.getByRole('button', { name: /Governance Insights/ }).click();
    await expect(page.getByText('Governance & Learning Insights')).toBeVisible();

    const kpiValue = page.locator('.kpi', { hasText: 'Final decisions' }).locator('.v');
    await expect(kpiValue).toBeVisible();
    const count = parseInt((await kpiValue.textContent()).trim(), 10);
    expect(count).toBeGreaterThanOrEqual(1);
  });
});
