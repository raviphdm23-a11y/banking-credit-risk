# AIRB Credit Risk Calculator - Web Application

## 📋 Overview
A professional, browser-based AIRB (Advanced Internal Ratings Based) calculator for credit risk analysis. Fully compliant with Basel III methodology.

## ✨ Features
- **Real-time AIRB Calculations** - Automatic RWA and capital requirement calculations
- **Portfolio Management** - Add, view, and manage multiple loans
- **Summary Dashboard** - View key metrics and regulatory ratios
- **Data Export** - Export portfolio data to CSV or JSON
- **Mobile Responsive** - Works on desktop, tablet, and mobile devices
- **No Backend Required** - Runs entirely in the browser
- **Basel III Compliant** - Uses proper correlation adjustments and maturity factors

## 📁 Project Structure
```
Banking_Credit_Risk/
├── index.html                  # Main web application (single file)
├── AIRB_Credit_Risk_Template.xlsx  # Excel template (reference)
└── DEPLOYMENT_GUIDE.md         # This file
```

## 🚀 Quick Start (Local)

### Option 1: Direct File Opening
1. Open `index.html` in any modern web browser
2. Start adding loans and analyzing credit risk

### Option 2: Using Python (Simple HTTP Server)
```bash
# Navigate to the project folder
cd "C:\Users\Arnav\OneDrive\Desktop\Daily reading\Banking_Credit_Risk"

# Start a local server (Python 3)
python -m http.server 8000

# Open browser to: http://localhost:8000
```

### Option 3: Using Node.js (http-server)
```bash
# Install http-server globally
npm install -g http-server

# Navigate to project folder and start server
cd "C:\Users\Arnav\OneDrive\Desktop\Daily reading\Banking_Credit_Risk"
http-server

# Open browser to the provided address
```

---

## 🌐 Deployment to Web

### Option 1: GitHub Pages (FREE - Recommended)

1. **Create a GitHub Account** (if you don't have one)
   - Go to github.com and sign up

2. **Create a New Repository**
   - Repository name: `airb-calculator`
   - Make it Public
   - Do NOT initialize with README

3. **Upload Files**
   ```bash
   # In PowerShell, navigate to project folder
   cd "C:\Users\Arnav\OneDrive\Desktop\Daily reading\Banking_Credit_Risk"
   
   # Initialize git
   git init
   
   # Add GitHub remote (replace USERNAME with your GitHub username)
   git remote add origin https://github.com/USERNAME/airb-calculator.git
   
   # Add and commit files
   git add index.html
   git commit -m "Add AIRB Calculator"
   
   # Push to GitHub
   git branch -M main
   git push -u origin main
   ```

4. **Enable GitHub Pages**
   - Go to repository Settings → Pages
   - Source: Deploy from a branch
   - Branch: main, folder: / (root)
   - Save

5. **Access Your App**
   - URL: `https://USERNAME.github.io/airb-calculator`
   - Share this link with users

---

### Option 2: Netlify (FREE with Custom Domain Support)

1. **Sign Up**
   - Go to netlify.com
   - Sign up with GitHub/Google

2. **Deploy Files**
   - Drag and drop `index.html` to Netlify
   - OR connect your GitHub repository

3. **Get Public URL**
   - Netlify provides a public URL automatically
   - Customize domain in settings

---

### Option 3: Vercel (FREE)

1. **Sign Up**
   - Go to vercel.com
   - Sign up with GitHub

2. **Import Project**
   - Connect your GitHub repository
   - Vercel auto-deploys on push

3. **Access App**
   - Get automatic URL like `airb-calculator.vercel.app`

---

### Option 4: AWS S3 + CloudFront (AFFORDABLE)

1. **Create S3 Bucket**
   ```bash
   # Using AWS CLI
   aws s3 mb s3://airb-calculator-prod
   ```

2. **Upload HTML File**
   ```bash
   aws s3 cp index.html s3://airb-calculator-prod/
   ```

3. **Enable Static Website Hosting**
   - S3 Bucket Settings → Static website hosting
   - Index document: `index.html`

4. **Create CloudFront Distribution**
   - Origin: Your S3 bucket
   - Default root object: `index.html`

5. **Access via CloudFront URL**
   - Example: `d123abc.cloudfront.net`

---

### Option 5: Heroku (SIMPLE - $5-7/month)

```bash
# Install Heroku CLI
# Create Procfile in project root:
echo "web: python -m http.server \$PORT" > Procfile

# Deploy
heroku create airb-calculator
git push heroku main
```

---

## 🔒 Security Considerations

### ✅ Current Implementation (Browser-Only)
- ✓ No data sent to servers
- ✓ All calculations happen locally
- ✓ Suitable for internal use
- ✓ GDPR compliant (no data collection)

### 🛡️ For Production (With Backend)
If you want to add data persistence and multi-user support:

1. **Add Authentication** - User login system
2. **Add Database** - Store portfolios (MongoDB, PostgreSQL)
3. **API Layer** - Node.js/Python backend
4. **Encryption** - SSL/TLS for data in transit
5. **Audit Trail** - Log all calculations

---

## 💾 Data Management

### Export Options
- **CSV** - Import to Excel for further analysis
- **JSON** - For integration with other systems

### Import (Manual)
- Users can manually enter loan data into the web form
- Future enhancement: Add bulk import from CSV

---

## 🔧 Technical Requirements

### Browser Compatibility
- Chrome 90+
- Firefox 88+
- Safari 14+
- Edge 90+
- Mobile browsers (iOS Safari 12+, Chrome Android)

### No Dependencies
- Pure HTML5
- Vanilla JavaScript (no frameworks)
- No external libraries
- Works offline (after initial load)

---

## 📊 AIRB Calculation Formula

The application implements Basel III AIRB methodology:

```
Correlation = MIN(0.03 + 0.12 × (1 - EXP(-50 × PD)), 0.999)

Maturity Adjustment = (1 + (M-1) × 0.14) / (1 - 1.5 × 0.14)

RWA = EAD × [PD × LGD × Adjustment × 1.06 - PD × LGD] × 12.5

Capital Requirement = RWA × 8%
```

---

## 🎓 Regulatory Ratios

The calculator displays:
- **CET1 Requirement**: 4.5% of RWA
- **Tier 1 Requirement**: 6.0% of RWA
- **Total Capital**: 8.0% of RWA (minimum)
- **RWA Density**: Total RWA as % of Total EAD

---

## 📞 Support & Updates

### Enhancements (Future)
- [ ] Multi-user accounts with portfolios
- [ ] Data persistence (Cloud storage)
- [ ] Bulk import from CSV
- [ ] Report generation (PDF)
- [ ] Scenario analysis
- [ ] Backtesting metrics
- [ ] API for third-party integration

### Bug Reports
- Document the issue
- Note browser and OS
- Include test data

---

## 📄 License
Free to use and modify for internal banking use.

---

## 🎉 Quick Deployment Checklist

- [ ] Test locally (open index.html in browser)
- [ ] Choose deployment platform
- [ ] Set up deployment account
- [ ] Upload index.html file
- [ ] Verify public URL is accessible
- [ ] Share URL with users
- [ ] Monitor for any issues
- [ ] Add custom domain (optional)

---

## 📧 Questions?

For support or customization requests, document your needs and share test cases.

**Version**: 1.0
**Last Updated**: June 2026
**Basel III Compliant**: ✓
