# Relationship Management — Playwright E2E tests

Self-contained browser tests for the RM cockpit (`/relationship/`). Everything —
dependencies **and** the Chromium binary — lives inside this folder, so you can
remove the whole thing with one command when you're done.

## What it covers
1. **Accept & finalise** — a strong applicant is accepted; case becomes `DECISION_FINAL`.
2. **Reject rationale gate** — a rejection with < 20 chars is blocked; a proper rationale finalises a `DECLINE`.
3. **PDF reports + versioning** — a report generates, the link serves a real PDF, and regenerating keeps the prior version.
4. **Governance insights** — a finalised decision shows up in the insights KPIs.

Every case it creates is named `PWTEST …`; a global teardown deletes those
cases (and their generated PDFs) from `bank.db` after the run.

## Prerequisites
- The Flask app must be running at `http://127.0.0.1:5000`
  (`.\run_flask.ps1` or `.\venv310\Scripts\python.exe app.py` from the project root).

## Install (one-time)
```bash
cd testing/rm-e2e
npm install
PLAYWRIGHT_BROWSERS_PATH=0 npx playwright install chromium
```
`PLAYWRIGHT_BROWSERS_PATH=0` puts the browser inside `node_modules` instead of a
global cache (the config also sets this at runtime).

## Run
```bash
npm test            # headed (watch it run), per playwright.config.js
npm run report      # open the HTML report (videos + traces) afterwards
```

## Clean up
```bash
# from the project root — removes deps, browser, reports, everything:
rm -rf testing/rm-e2e
```
Test data is auto-purged from `bank.db` by the teardown; to do it manually:
`..\..\venv310\Scripts\python.exe cleanup.py`
