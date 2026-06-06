# Loan Approval Workflow - Quick Start

## The New Feature: One-Click Loan Approval

### 🎯 What You Can Do Now

Calculate PD → **Click "Proceed"** → Auto-fill main calculator → Enter remaining details → Calculate RWA

---

## Visual Workflow

```
┌──────────────────────────────────────────────────────────────┐
│                                                              │
│  STEP 1: PD CALCULATOR                                      │
│  ═════════════════════════════════════════════════════════ │
│                                                              │
│  📊 Enter Financial Metrics:                                │
│     • Debt-to-Equity Ratio       [0.8]                    │
│     • Interest Coverage Ratio    [3.5]                    │
│     • Profitability Margin (%)   [18]                     │
│     • Liquidity Ratio            [1.2]                    │
│                                                              │
│  [Calculate PD]                                             │
│                                                              │
└──────────────────────────────────────────────────────────────┘
                          ⬇️
┌──────────────────────────────────────────────────────────────┐
│                                                              │
│  STEP 2: REVIEW PD RESULT                                  │
│  ═════════════════════════════════════════════════════════ │
│                                                              │
│  ✅ Probability of Default: 3.79%                           │
│  Risk Level: 🟢 Low Risk                                    │
│                                                              │
│  "Do you want to proceed with this loan?"                   │
│                                                              │
│  [✅ Yes, Proceed] [❌ No, Cancel]                          │
│                    ↓ Click YES ↓                            │
│                                                              │
└──────────────────────────────────────────────────────────────┘
                          ⬇️  (Automatic)
┌──────────────────────────────────────────────────────────────┐
│                                                              │
│  STEP 3: MAIN CALCULATOR (Auto-Populated)                  │
│  ═════════════════════════════════════════════════════════ │
│                                                              │
│  ✅ Notification: Data loaded from PD Calculator           │
│                                                              │
│  Common Fields (✅ Pre-filled):                            │
│  • Loan ID:           [CORP001]        ✅                  │
│  • Borrower Name:     [ABC Corp]       ✅                  │
│  • Exposure Amount:   [________]       👈 FILL THIS        │
│                                                              │
│  AIRB Parameters (Fill remaining):                         │
│  • Sector:            [Select...]      👈 FILL THIS        │
│  • PD (%):            [3.79]           ✅                  │
│  • LGD (%):           [________]       👈 FILL THIS        │
│  • Maturity (Years):  [________]       👈 FILL THIS        │
│                                                              │
│  [Add Loan]                                                 │
│                                                              │
└──────────────────────────────────────────────────────────────┘
                          ⬇️
┌──────────────────────────────────────────────────────────────┐
│                                                              │
│  STEP 4: RESULTS                                            │
│  ═════════════════════════════════════════════════════════ │
│                                                              │
│  RWA:                    $1,234,567                         │
│  Capital Required (8%):  $98,765                            │
│  Risk Density:           45.3%                              │
│                                                              │
│  ✅ Loan added to portfolio                                 │
│  ✅ Summary updated                                         │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

---

## How to Use (3 Steps)

### Step 1: Calculate PD
```
📊 PD Calculator
├─ Enter: Borrower ID (e.g., CORP001)
├─ Enter: Borrower Name (e.g., ABC Manufacturing)
├─ Enter: 4 Financial Metrics
│  ├─ Debt-to-Equity Ratio
│  ├─ Interest Coverage Ratio
│  ├─ Profitability Margin (%)
│  └─ Liquidity Ratio (Current Ratio)
└─ Click: [Calculate PD]
```

### Step 2: Approve Loan
```
✅ Review PD Result
   • See calculated PD percentage
   • See Risk Level (Very Low → Very High)
   • See Component Breakdown

📋 Decision Point
   • Click: [✅ Yes, Proceed with Loan]
          OR
   • Click: [❌ No, Cancel]
```

### Step 3: Main Calculator (Auto-Populated)
```
✅ Auto-filled fields:
   ✓ Loan ID
   ✓ Borrower Name
   ✓ PD (%)

👤 You fill in remaining:
   • Exposure Amount
   • Sector
   • LGD (%)
   • Maturity
   
[Add Loan] → Results!
```

---

## Key Points

✨ **One-Click Transfer**
- Click "Yes, Proceed" to transfer data
- No manual copying needed
- No page redirects visible to user

✨ **Auto-Population**
- 3 fields pre-filled automatically
- Other fields stay empty for your input
- Green notification confirms data received

✨ **Error Recovery**
- Click "No, Cancel" to go back
- Recalculate as needed
- No data is lost

✨ **Secure & Private**
- Data stored on your device only
- No server uploads
- Works offline
- Automatically cleared after use

---

## Common Scenarios

### Scenario 1: Approve & Process Loan
```
1. Open PD Calculator
2. Enter financial metrics for XYZ Corp
3. Click [Calculate PD] → Shows 5.23% (Medium Risk)
4. Click [✅ Yes, Proceed] → Auto-redirects
5. Main calculator opens with auto-filled data
6. Fill: Exposure=2M, Sector=Tech, LGD=50%, Maturity=3
7. Click [Add Loan] → Results calculated!
```

### Scenario 2: Recalculate Before Approving
```
1. Open PD Calculator
2. Enter financial metrics
3. Click [Calculate PD] → Shows 15% (High Risk)
4. Click [❌ No, Cancel] → Stay on calculator
5. Modify inputs (e.g., update profitability)
6. Click [Calculate PD] → Shows 8% (Medium Risk)
7. Click [✅ Yes, Proceed] → Now transfer
```

### Scenario 3: Skip PD Calculator
```
1. Go directly to Main Calculator
2. Manually enter all loan details
3. Works as before (no PD calculator data)
4. Click [Add Loan] → Results calculated!
```

---

## What Gets Transferred?

**From PD Calculator → Main Calculator:**
- ✅ Borrower ID
- ✅ Borrower Name  
- ✅ Calculated PD (%)

**Everything Else:**
- You enter manually in main calculator
- Exposure Amount
- Sector / Category
- LGD
- Maturity
- Collateral (if applicable)

---

## Tips for Best Results

1. **Accurate Financial Data**
   - Use latest annual statements
   - Ensure consistent definitions

2. **Review Risk Level**
   - Very Low: Standard lending terms
   - Low: Standard lending terms
   - Medium: Enhanced monitoring recommended
   - High: Strong covenants needed
   - Very High: Restrict or decline

3. **Complete the Form**
   - Don't skip any required fields
   - Use realistic values
   - Round to appropriate decimals

4. **Save Your Work**
   - Portfolio automatically saved to browser storage
   - Use Export to backup (CSV/JSON)
   - Clear browser cache carefully (clears data)

---

## Troubleshooting

**Q: Data not appearing in main calculator?**
A: Check browser's localStorage is enabled. Or manually enter the information.

**Q: Want to process multiple loans?**
A: Process one loan at a time. Each approval overwrites the previous data.

**Q: Can I go back to PD calculator after approval?**
A: Yes! Browser's back button works. But data won't be transferred again.

**Q: What if I made a mistake?**
A: No problem! Edit any field and recalculate. The system allows changes.

---

## Files Updated

- ✅ `pd-calculator.html` - Added approval buttons
- ✅ `index.html` - Added auto-load functionality

**New Files Added:**
- 📄 `LOAN_APPROVAL_WORKFLOW.md` - Complete documentation
- 📄 `QUICK_START_WORKFLOW.md` - This file

---

## Get Started Now!

1. Open `pd-calculator.html` in your browser
2. Enter a borrower's financial metrics
3. Click "Calculate PD"
4. Click "✅ Yes, Proceed with Loan"
5. Watch as data auto-populates in the main calculator!

---

**Version:** 1.0 | **Status:** ✅ Ready to Use | **Updated:** June 3, 2026
