/* ───────────────────────────────────────────────────────────────────────────
 * _dev/autofill.js  —  TEMPORARY DEV-ONLY TEST HELPER (safe to delete anytime)
 * ---------------------------------------------------------------------------
 * Injects a floating "🎲 Auto-fill (DEV)" button into the Credit Risk Calculator
 * (borrower-info.html). Clicking it populates EVERY field with random but valid
 * test data so you can exercise the calculator / Send-to-RM / report buttons fast
 * without typing. Sequenced fields increment on each click (CORP-001, CORP-002…).
 *
 * This file is self-contained and self-injecting. To remove the feature entirely:
 *   1. delete the  <script src=".../_dev/autofill.js">  line in public/borrower-info.html
 *   2. delete the  public/_dev/  folder
 * Nothing else references it. It is also excluded from GCP deploy (.gcloudignore).
 * ─────────────────────────────────────────────────────────────────────────── */
(function () {
  if (window.__devAutofillLoaded) return;
  window.__devAutofillLoaded = true;

  const $    = (id) => document.getElementById(id);
  const rnd  = (min, max) => Math.random() * (max - min) + min;
  const ri   = (min, max) => Math.floor(rnd(min, max + 1));      // random int [min,max]
  const r2   = (min, max) => Math.round(rnd(min, max) * 100) / 100;
  const r1   = (min, max) => Math.round(rnd(min, max) * 10) / 10;
  const step = (v, s) => Math.round(v / s) * s;
  const pick = (arr) => arr[ri(0, arr.length - 1)];

  const NAMES = ['Apex Industries Ltd', 'Meridian Traders', 'Cobalt Foods Pvt Ltd',
    'Harbour Logistics', 'Nova Textiles', 'Sterling Motors', 'Vertex Pharma',
    'Crescent Steel', 'Orchid Retail', 'Pioneer Agro', 'Summit Engineering'];

  function setVal(id, val) {
    const el = $(id);
    if (!el) return;
    el.value = val;
    el.dispatchEvent(new Event('input',  { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
  }

  function randomSelect(id) {
    const el = $(id);
    if (!el || el.tagName !== 'SELECT') return;
    const opts = Array.from(el.options).filter((o) => o.value !== '');
    if (!opts.length) return;
    el.value = pick(opts).value;
    el.dispatchEvent(new Event('change', { bubbles: true }));
  }

  function fillAll() {
    // sequential counter — persists across clicks so IDs march CORP-001, CORP-002, …
    const seq = (parseInt(localStorage.getItem('dev_autofill_seq') || '0', 10) || 0) + 1;
    localStorage.setItem('dev_autofill_seq', String(seq));
    const pad = String(seq).padStart(3, '0');

    // Basic info
    setVal('borrowerId',     'CORP-' + pad);
    setVal('borrowerName',   pick(NAMES) + ' ' + pad);
    setVal('exposureAmount', step(ri(100000, 50000000), 1000));

    // 4 explainable financial ratios
    setVal('debtToEquity',       r2(0.2, 3.5));
    setVal('interestCoverage',   r2(0.5, 12));
    setVal('profitabilityMargin', r1(-5, 30));
    setVal('liquidityRatio',     r2(0.4, 3.5));

    // KYC / bureau numerics (kept inside the form's validation bounds)
    setVal('kycAge',              ri(21, 65));        // 18–100
    setVal('kycYearsEmployed',    ri(0, 35));
    setVal('kycAnnualIncome',     step(ri(300000, 8000000), 10000)); // ≥ 1,00,000
    setVal('kycFoir',             r2(0.10, 0.75));    // 0.00–0.90
    setVal('kycNumDependents',    ri(0, 4));
    setVal('kycCibilScore',       ri(550, 820));      // 300–900
    setVal('kycMonthsAsCustomer', ri(0, 180));
    setVal('kycLatePayments',     ri(0, 6));          // 0–12
    setVal('kycExistingLoans',    ri(0, 5));
    setVal('kycExistingProducts', ri(0, 6));

    // Onboarding & compliance numerics
    setVal('proposedEmi',          step(ri(5000, 90000), 500));
    setVal('existingObligations',  step(ri(0, 50000), 500));

    // KYC status & screening — biased to the happy path so a sanctions hit doesn't block
    // most test runs, but PEP/sanctions still appear occasionally to exercise those gates.
    setVal('kycStatusField', Math.random() < 0.9 ? 'Verified' : 'Pending');
    const r = Math.random();
    setVal('screeningField', r < 0.85 ? 'clean' : (r < 0.95 ? 'pep' : 'sanctions'));

    // Dropdowns — pick a random valid (non-placeholder) option. Includes country
    // (jurisdiction) so the referral payload carries it.
    ['sector', 'country', 'kycEmploymentType', 'kycCityTier', 'kycEducation',
     'kycResidenceType', 'kycLoanPurpose', 'kycPreviousDefault', 'kycIsRural',
     'seniority', 'collateralType', 'externalRating', 'exposureCategory'].forEach(randomSelect);

    // Collateral: ~55% of cases secured
    setVal('collateralValue', Math.random() < 0.55 ? step(ri(200000, 40000000), 1000) : 0);

    // Methodology radio — random among AIRB / Standardized / Both to exercise all paths
    const radio = $(pick(['modeAIRB', 'modeSA', 'modeBoth']));
    if (radio) { radio.checked = true; radio.dispatchEvent(new Event('change', { bubbles: true })); }

    // loanType's change handler auto-overwrites maturity, so set loanType FIRST then maturity LAST
    randomSelect('loanType');
    setVal('maturityOverride', r1(1, 5));
  }
  window.devAutofill = fillAll;

  function injectButton() {
    if ($('devAutofillBtn')) return;
    const b = document.createElement('button');
    b.id = 'devAutofillBtn';
    b.type = 'button';
    b.textContent = '🎲 Auto-fill (DEV)';
    b.title = 'Populate all fields with random valid test data (IDs increment each click). Temporary dev helper.';
    b.style.cssText =
      'position:fixed;bottom:20px;right:20px;z-index:99999;background:#7c3aed;color:#fff;' +
      'border:none;border-radius:30px;padding:12px 20px;font:600 14px system-ui;cursor:pointer;' +
      'box-shadow:0 6px 20px rgba(124,58,237,.45);';
    b.onmouseenter = () => (b.style.opacity = '.9');
    b.onmouseleave = () => (b.style.opacity = '1');
    b.onclick = fillAll;
    document.body.appendChild(b);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', injectButton);
  else injectButton();
})();
