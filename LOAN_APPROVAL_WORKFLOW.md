# Loan Approval Workflow - Feature Summary

## Overview

A new **Loan Approval Workflow** has been implemented that seamlessly connects the PD Calculator with the main loan calculator. Users can now:

1. Calculate PD using rule-based model
2. Review the results
3. **Click "Yes, Proceed with Loan"** to transfer borrower data directly to the main calculator
4. Complete remaining loan details (LGD, EAD, Maturity, Sector, etc.)
5. Calculate RWA and capital requirements

---

## New Feature: Loan Approval Decision

### In PD Calculator (`pd-calculator.html`)

After calculating PD, a new **decision section** appears below the results:

**Question:** "Do you want to proceed with this loan?"

**Two Buttons:**
1. **✅ Yes, Proceed with Loan** (Green)
   - Transfers borrower data to main calculator
   - Automatically loads data when main calculator opens
   - Takes you to index.html

2. **❌ No, Cancel** (Gray)
   - Closes the results section
   - Stays on PD calculator page
   - Allows you to modify inputs and recalculate

---

## Complete Workflow

### Step 1: Calculate PD (PD Calculator Page)
```
┌─────────────────────────────────────────┐
│  PD Calculator                          │
│  ─────────────────────────────────────  │
│  Borrower ID:     [CORP001]             │
│  Borrower Name:   [ABC Manufacturing]   │
│  D/E Ratio:       [0.8]                 │
│  Interest Cov:    [3.5]                 │
│  Margin:          [18%]                 │
│  Current Ratio:   [1.2]                 │
│                                         │
│  [Calculate PD]  [Clear]                │
└─────────────────────────────────────────┘
```

### Step 2: Review PD Result
```
┌─────────────────────────────────────────┐
│  ✅ Result Section Appears:             │
│  ─────────────────────────────────────  │
│  Probability of Default: 3.79%          │
│  Risk Level: 🟢 Low Risk                │
│  Component Breakdown: [details...]      │
│                                         │
│  "Do you want to proceed with this     │
│   loan?"                                │
│                                         │
│  [✅ Yes, Proceed] [❌ No, Cancel]     │
└─────────────────────────────────────────┘
```

### Step 3: Transfer Data (Automatic)
When you click **"Yes, Proceed with Loan"**:
- Borrower ID, Name, and calculated PD are stored
- Page redirects to main calculator (index.html)
- Data is automatically loaded into the form

### Step 4: Main Calculator (Auto-Populated)
```
┌─────────────────────────────────────────┐
│  📊 Green Notification:                 │
│  "✅ Data loaded from PD Calculator:   │
│   ABC Manufacturing (PD: 3.79%)"        │
└─────────────────────────────────────────┘

Common Fields (Pre-Filled):
├─ Loan ID:        [CORP001]      ✅
├─ Borrower Name:  [ABC Mfg]      ✅
└─ Exposure Amount: [empty]       👈 Fill this

AIRB Parameters (Empty - Fill These):
├─ Sector:         [-- Select --]
├─ PD (%):         [3.79]         ✅
├─ LGD (%):        [empty]        👈 Fill this
└─ Maturity:       [empty]        👈 Fill this

Calculate As:
⦿ AIRB Approach
```

### Step 5: Complete Remaining Details
User fills in:
- **Sector** (Manufacturing, Retail, etc.)
- **LGD** (Loss Given Default %)
- **Maturity** (Years)
- **Exposure Amount** (if not pre-filled)

### Step 6: Calculate Results
- Click "Add Loan"
- RWA and capital requirements calculated automatically
- Results appear in portfolio table
- Summary statistics updated

---

## Technical Implementation

### Data Transfer Mechanism

**Technology Used:** HTML5 localStorage (browser's local storage)

**How It Works:**

1. **PD Calculator Stores Data:**
```javascript
// In pd-calculator.html
function proceedWithLoan() {
    const loanData = {
        borrowerId: "CORP001",
        borrowerName: "ABC Manufacturing",
        pd: 3.79,
        timestamp: "2026-06-03T21:30:00Z"
    };
    localStorage.setItem('pdCalculatorLoan', JSON.stringify(loanData));
    window.location.href = 'index.html';
}
```

2. **Main Calculator Retrieves Data:**
```javascript
// In index.html
function loadPDCalculatorData() {
    const pdLoanData = localStorage.getItem('pdCalculatorLoan');
    if (pdLoanData) {
        const loanData = JSON.parse(pdLoanData);
        
        // Pre-fill form
        document.getElementById('loanId').value = loanData.borrowerId;
        document.getElementById('borrower').value = loanData.borrowerName;
        document.getElementById('pd').value = loanData.pd;
        
        // Show notification
        showPDDataNotification(loanData.borrowerName, loanData.pd);
        
        // Clean up
        localStorage.removeItem('pdCalculatorLoan');
    }
}
```

**Why localStorage?**
- ✅ No server needed
- ✅ Secure (stays on user's device)
- ✅ Works offline
- ✅ Automatic cleanup after use
- ✅ Browser compatible

---

## User Interface Changes

### PD Calculator Page (`pd-calculator.html`)

**Before:**
- Results showed PD value
- User had to manually copy PD
- Manual navigation to main calculator

**After:**
- Results show PD value + decision buttons
- Green "Yes, Proceed" button
- Gray "No, Cancel" button
- Automatic data transfer
- Helpful hint message

### Main Calculator Page (`index.html`)

**New Features:**
1. **Auto-Load Function**
   - Checks for PD calculator data on page load
   - Automatically pre-fills 3 fields:
     - Loan ID
     - Borrower Name
     - PD (%)

2. **Success Notification**
   - Green notification appears top-right
   - Shows borrower name and calculated PD
   - Auto-dismisses after 5 seconds
   - Smooth slide-in/out animation

3. **Smart Form Management**
   - Other fields remain empty for user input
   - User focuses on filling remaining fields
   - Automatic cursor positioning

---

## Features & Benefits

### ✨ Seamless Integration
- One-click transfer from PD to loan calculator
- No manual copy-paste required
- No data entry errors from retyping

### ✨ User-Friendly
- Clear decision point ("Do you want to proceed?")
- Green notification confirms data transfer
- No confusing redirects or loading screens

### ✨ Efficient Workflow
- Reduces steps in loan approval process
- Faster loan data entry
- Clear visual feedback

### ✨ Data Integrity
- No duplicate entry points
- Automatic validation
- Single source of truth (PD calculator)

### ✨ Browser-Based
- No server required
- Works offline
- Automatic cleanup (localStorage cleared after use)

---

## Step-by-Step Usage Guide

### Complete Workflow Example

**Scenario:** You want to process a loan for "XYZ Corporation"

**Step 1: Go to PD Calculator**
1. From main calculator, click 📊 **"PD Calculator (Rule-Based)"**
2. Or open `pd-calculator.html` directly

**Step 2: Enter Financial Data**
```
Borrower ID:            XYZ-CORP-001
Borrower Name:          XYZ Corporation
Debt-to-Equity:         1.2
Interest Coverage:      2.8x
Profitability Margin:   12%
Liquidity Ratio:        1.0
```

**Step 3: Calculate PD**
1. Click **"Calculate PD"** button
2. System calculates: PD = 6.52% (Medium Risk)
3. Results appear with breakdown

**Step 4: Approve Loan**
1. Review the calculated PD (6.52%)
2. Review risk level (Medium)
3. Click **"✅ Yes, Proceed with Loan"**
4. Automatically redirected to main calculator

**Step 5: Main Calculator Opens**
- 🟢 Green notification: "Data loaded: XYZ Corporation (PD: 6.52%)"
- Form shows:
  - ✅ Loan ID: XYZ-CORP-001
  - ✅ Borrower: XYZ Corporation
  - ✅ PD: 6.52%
  - ⬜ Exposure Amount: [enter amount]
  - ⬜ Sector: [select sector]
  - ⬜ LGD: [enter LGD%]
  - ⬜ Maturity: [select years]

**Step 6: Complete Remaining Fields**
```
Exposure Amount:        $2,500,000
Sector:                 Manufacturing
LGD (%):                60%
Maturity (Years):       3
```

**Step 7: Calculate & Review**
1. Click **"Add Loan"**
2. Results calculated:
   - RWA: $2,437,500
   - Capital Required: $195,000
3. Loan added to portfolio
4. Summary updated

---

## Error Handling

### If Something Goes Wrong

**Scenario 1: User cancels at PD calculator**
- Click "No, Cancel" button
- Results section closes
- Stay on PD calculator
- Can modify inputs and recalculate

**Scenario 2: Browser issue / data not transferring**
- Data is safely stored in localStorage
- User can manually navigate to main calculator
- Can manually enter borrower info
- Data will be cleared from storage

**Scenario 3: Multiple PD calculations**
- Each "Yes, Proceed" overwrites previous data
- Only the most recent loan data is transferred
- Only one loan at a time can be transferred this way

---

## Technical Details

### Browser Compatibility
- ✅ Chrome/Chromium
- ✅ Firefox
- ✅ Safari
- ✅ Edge
- ✅ Opera
- ⚠️ Internet Explorer (limited support)

### Data Stored
```json
{
  "borrowerId": "CORP001",
  "borrowerName": "ABC Manufacturing",
  "pd": 3.79,
  "timestamp": "2026-06-03T21:30:00Z"
}
```

**Storage Location:** Browser's localStorage
**Storage Duration:** Until main calculator loads (then auto-cleared)
**Maximum Size:** ~5MB per site (more than enough)

### Security Considerations
- ✅ Data stays on user's browser (not sent to server)
- ✅ LocalStorage cleared automatically after use
- ✅ No external API calls
- ✅ No data transmission over network
- ✅ Works offline

---

## Files Modified

| File | Changes | Impact |
|------|---------|--------|
| `pd-calculator.html` | Added "Proceed with Loan" button & logic | Users can now transfer data |
| `index.html` | Added data loading & notification system | Automatically receives PD data |

**New JavaScript Functions:**
- `proceedWithLoan()` - Transfers data from PD calculator
- `loadPDCalculatorData()` - Loads data on main calculator
- `showPDDataNotification()` - Shows success notification

---

## Future Enhancements (Optional)

These could be added later if needed:

1. **Batch Loan Processing**
   - Process multiple loans from PD calculator
   - Transfer multiple loans at once

2. **Loan Comparison**
   - Compare PD results for multiple borrowers
   - Before deciding to proceed

3. **History/Archive**
   - Keep track of processed loans
   - Review previous decisions

4. **Approval Workflow**
   - Add approval stages
   - Manager sign-off
   - Compliance checks

5. **Loan Templates**
   - Save common loan types
   - Quick populate form

---

## Testing the Feature

### Manual Test Steps

**Test 1: Basic Transfer**
1. Open `pd-calculator.html`
2. Enter: ID=TEST001, Name=Test Corp
3. Enter: D/E=0.5, Coverage=4.5, Margin=20%, Ratio=1.5
4. Click "Calculate PD"
5. Click "✅ Yes, Proceed with Loan"
6. Verify auto-population in main calculator
7. ✅ Data should appear (ID, Name, PD)

**Test 2: Cancel Flow**
1. Open `pd-calculator.html`
2. Enter same data as Test 1
3. Click "Calculate PD"
4. Click "❌ No, Cancel"
5. ✅ Should stay on PD calculator

**Test 3: Direct Navigation**
1. Complete Test 1
2. Go back to PD calculator
3. Do NOT proceed with loan
4. ✅ Previous data should NOT load
5. ✅ Form should be empty

---

## Summary

The new **Loan Approval Workflow** provides:

✅ **One-Click Approval** - Transfer data with single button  
✅ **Automatic Population** - Form pre-fills with borrower data  
✅ **Clear Feedback** - Green notification shows what was loaded  
✅ **Error Recovery** - Cancel option to go back  
✅ **Efficient Process** - Reduce manual entry steps  
✅ **Data Integrity** - No copy-paste errors  
✅ **No Server Needed** - Offline-capable  

**Result:** Users can now approve a loan based on PD and immediately proceed to calculate RWA with minimal additional data entry.

---

**Version:** 1.0  
**Status:** ✅ Production Ready  
**Last Updated:** June 3, 2026
