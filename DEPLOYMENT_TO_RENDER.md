# Deploy Banking Credit Risk Calculator to Render.com

## Overview

This guide walks you through deploying the Banking Credit Risk Calculator to Render.com, making it accessible via a public URL that you can share with anyone.

**Result:** A URL like `https://banking-credit-risk.onrender.com` that anyone can open in a browser.

**Time to complete:** ~20 minutes (most of it is waiting for deployment)

---

## Prerequisites

- A GitHub account (free at https://github.com)
- A Render.com account (free at https://render.com, sign in with GitHub)
- Git installed on your computer (https://git-scm.com)
- You have already prepared these files (they're ready now):
  - `.gitignore`
  - `Procfile`
  - `runtime.txt`
  - Updated `requirements.txt` with gunicorn
  - Updated `app.py` with model pre-loading

---

## Step 1: Initialize Git Repository (Local)

Open **PowerShell** or **Command Prompt** and navigate to the project folder:

```powershell
cd "C:\Users\Arnav\OneDrive\Desktop\Daily reading\Banking_Credit_Risk"
```

Initialize git and stage your files:

```powershell
git init
```

Add the deployment files and source code:

```powershell
git add .gitignore Procfile runtime.txt requirements.txt app.py config.py
git add backend/ public/ ml_models/
git commit -m "Initial commit: Banking Credit Risk Calculator ready for deployment"
```

**Important:** Do NOT run `git add .` or `git add -A` — this would include the `venv/` folder (hundreds of MB) and test Excel files.

**Check your git status:**

```powershell
git status
```

You should see "nothing to commit, working tree clean".

---

## Step 2: Create GitHub Repository

1. Go to https://github.com/new
2. Fill in:
   - **Repository name:** `banking-credit-risk-calculator` (can be any name)
   - **Description:** (optional)
   - **Visibility:** Select **Private** (recommended — this contains financial logic)
3. Do NOT check "Initialize this repository with README" or any other options
4. Click **"Create repository"**

GitHub will show you two command blocks. You need the second one: "…push an existing repository". Copy those commands.

---

## Step 3: Push Code to GitHub (Local Terminal)

GitHub will show you commands like this:

```powershell
git remote add origin https://github.com/YOUR_USERNAME/banking-credit-risk-calculator.git
git branch -M main
git push -u origin main
```

Run these three commands in your PowerShell/Command Prompt. You may be prompted to log in to GitHub — authenticate when prompted.

**Verify:** Go back to your GitHub repository page (refresh it) — you should see your code files.

---

## Step 4: Deploy on Render.com

### 4.1 Sign In to Render

1. Go to https://render.com
2. Click **Sign in** → **Sign in with GitHub**
3. Authorize Render to access your GitHub account
4. You'll be redirected to your Render dashboard

### 4.2 Create Web Service

1. Click **"New +"** button → select **"Web Service"**
2. In "Connect a repository", you'll see your GitHub repositories
3. Click the **"Connect"** button next to `banking-credit-risk-calculator`

### 4.3 Configure the Service

Fill in these settings:

| Field | Value |
|-------|-------|
| **Name** | `banking-credit-risk` (becomes your URL) |
| **Environment** | Python 3 |
| **Region** | Singapore (closest to India, better latency) |
| **Branch** | main |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `gunicorn app:app` |
| **Instance Type** | Free |

Leave all other settings as default.

### 4.4 Set Environment Variables

Scroll down to the **"Environment"** section and click **"Add Environment Variable"**

Add two variables:

| Key | Value |
|-----|-------|
| `FLASK_ENV` | `production` |
| `SECRET_KEY` | Generate a random 20+ character string, e.g. `bk8xP2mQnR7vLcW3jdA5X9mL2` |

For `SECRET_KEY`, you can use any random string. No special characters needed. Just make it long.

### 4.5 Deploy

Click **"Create Web Service"** at the bottom right.

Render will:
1. Clone your GitHub repository
2. Install dependencies (pip install -r requirements.txt)
3. Start the Flask server with gunicorn
4. Assign a URL

This takes 3-5 minutes. You'll see a progress log on the screen.

---

## Step 5: Verify Deployment

Once Render shows "Live" status, your app is running!

### 5.1 Find Your URL

Your URL is shown at the top of the Render service page, typically:

```
https://banking-credit-risk.onrender.com
```

(The exact subdomain depends on what you named it in Step 4.3)

### 5.2 Test the API Endpoints

Open your browser and visit these URLs:

**Health Check:**
```
https://banking-credit-risk.onrender.com/api/health
```
Expected response:
```json
{
  "status": "healthy",
  "service": "Banking Credit Risk Calculator API",
  "version": "1.0.0",
  "environment": "production"
}
```

**Model Info:**
```
https://banking-credit-risk.onrender.com/api/model-info
```
Expected response:
```json
{
  "status": "available",
  "model_path": "ml_models/pd_model.pkl",
  "metadata": {
    "model_type": "RandomForestRegressor",
    "version": "1.0.0",
    ...
  }
}
```

**Main App:**
```
https://banking-credit-risk.onrender.com/
```
Should load the borrower assessment form in your browser.

---

## Step 6: Share the Link

Your app is now live! Share this URL:

```
https://banking-credit-risk.onrender.com
```

Anyone can open it and:
- Enter borrower information
- Calculate PD using Rule-Based or Machine Learning methods
- Compare AIRB vs Standardized Approach
- Build a portfolio of loans
- Export results to CSV/JSON

---

## Important Notes

### Cold Start (First Visit)
The free tier on Render sleeps after 15 minutes of no traffic. When someone visits after the app has been sleeping:
- First visit takes ~30-50 seconds to load
- The app is "waking up" — this is normal
- Subsequent visits are instant (the app stays awake while being used)

**User experience:** Share this note with people you send the link to so they're not surprised by the initial wait.

### Updating Code
If you make changes to the code later:

1. Commit changes locally:
```powershell
git add <changed files>
git commit -m "Your commit message"
```

2. Push to GitHub:
```powershell
git push
```

3. Render auto-detects the push and redeploys automatically (takes 2-3 minutes)

### View Logs
To debug any issues:
1. Go to your Render service page
2. Click **"Logs"** tab
3. See real-time app logs and any errors

---

## Troubleshooting

### Issue: Deployment fails with Python error
**Solution:** Check that `runtime.txt` contains exactly `python-3.12.0`. Render must match the Python version used.

### Issue: Model not loading (404 error on /api/model-info)
**Solution:** Ensure `ml_models/pd_model.pkl` was committed to git. Run:
```powershell
git log --name-status
```
and check that `ml_models/pd_model.pkl` appears in the initial commit.

### Issue: "PermissionError: [Errno 13] Permission denied"
**Solution:** This is rare on Render's free tier. If it happens, the issue is likely a file permissions problem. Contact Render support or try redeploying.

### Issue: App shows "Service Unavailable" after 15 minutes of inactivity
**Solution:** This is expected behavior for Render's free tier. Visit the URL again — it will wake up in 30-50 seconds.

---

## Production Checklist

After deployment, review these items:

- [ ] All three test URLs (health, model-info, home page) respond correctly
- [ ] Calculations work in the browser (try both Rule-Based and ML methods)
- [ ] Portfolio recording and export work
- [ ] Share the URL with stakeholders
- [ ] Document the URL in a shared location (email, wiki, etc.)

### For Future Improvements

To use a **real trained ML model** instead of the demo:

1. Collect 3-5 years of historical borrower data with actual default outcomes
2. Run `python train_pd_model.py` locally with real data
3. Commit the updated `ml_models/pd_model.pkl` to git
4. Push to GitHub — Render redeploys automatically with the new model

---

## Contact & Support

**Questions about this deployment?**
- Check the Render.com documentation: https://render.com/docs
- Check Flask documentation: https://flask.palletsprojects.com
- Review the `ML_MODEL_GUIDE.md` for model-specific questions

**Ready to proceed?**

Follow the steps above in order. The entire process typically takes 20-30 minutes (mostly waiting for Render to build and deploy).

Once complete, you'll have a shareable URL for the Banking Credit Risk Calculator!
