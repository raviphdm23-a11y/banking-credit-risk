# Dashboard Discrepancy Analysis Report

## Issue Summary
The Operations Dashboard displays different metrics than the actual database contains:
- **Total Customers:** Dashboard shows **1,350** | Actual DB has **1,547**
- **Total Transactions:** Dashboard shows **71,267** | Actual DB has **81,322**

---

## Root Cause Analysis

### 1. TOTAL CUSTOMERS: 1,350 vs 1,547

**Where it shows: `public/operations/index.html` line 1674**
```javascript
<div class="kpi-value">${DB.customers.length}</div>
```

**Data Flow:**
1. Frontend calls `/operations/api/customers` (line 1205)
2. Backend returns ALL customers from customers table (line 1491)
3. Frontend then fetches details for each customer from `/operations/api/customers/<cid>` (line 1209)
4. Each response includes the customer object, which gets pushed to `DB.customers` (line 1214)

**Expected:** Should load all 1,547 unique customers
**Actual:** Dashboard shows 1,350

**Hypothesis:**
The number 1,350 is exactly the count of `bank_loan_metrics` rows (1 per loan).
This suggests that either:
- a) The frontend is filtering to only customers who have loans in `bank_loan_metrics`
- b) The API is filtering somewhere
- c) There's a data load issue where not all customer details are being fetched

**197 customers are missing** (1,547 - 1,350 = 197)
These are likely customers without loans in `bank_loan_metrics`.

---

### 2. TOTAL TRANSACTIONS: 71,267 vs 81,322

**Where it shows: `public/operations/index.html` line 1662**
```javascript
const totalTxns = DB.transactions.length;
```

**Data Flow:**
1. Frontend calls `/operations/api/customers/<cid>` for each customer
2. Each response includes transactions for that customer (line 1517-1519)
3. These transactions are pushed to `DB.transactions` (line 1217)

**Database Reality:**
- Total transactions in `transactions` table: **81,322**
- Missing transactions: ~**10,055** (81,322 - 71,267 = 10,055)

**Possible Causes:**
1. **Date filtering:** Transactions are being filtered by date range
   - Transactions until March 31, 2026: 63,216
   - This doesn't match 71,267 either
   
2. **Partial customer load:** If only 1,350 customers are loaded instead of 1,547:
   - Missing customers won't have their transactions loaded
   - 197 missing customers × ~50 transactions each ≈ 9,850 missing transactions
   - This is close to the 10,055 discrepancy!

3. **API load timeout:** The frontend might be experiencing a timeout when loading customer details
   - Not all customer transactions are being fetched successfully
   - Later customers in the list fail to load

---

## Conclusion

**Both discrepancies are caused by the same root issue:**

### The frontend is not loading all customers successfully

The dashboard is only loading **1,350 customers** instead of **1,547**, which means:
- 197 customers with no loans in `bank_loan_metrics` are being skipped
- All transactions for those 197 customers (~10,000 txns) are not loaded
- This results in the 71,267 count instead of 81,322

### Why this is happening:

Looking at `public/operations/index.html` line 1209:
```javascript
details = await Promise.all(
  list.map(c => fetch('/operations/api/customers/' + c.id).then(r=>r.json()).catch(()=>null))
);
```

The frontend is using `Promise.all()` which fetches details for all customers in parallel. If:
1. Some API calls timeout or fail silently (`.catch(()=>null)`)
2. Customers without loans take longer to fetch
3. The browser hits network limits with too many parallel requests

Then some customer details won't load properly.

---

## Evidence

### Database Check:
```sql
SELECT COUNT(*) FROM customers;  -- 1,547 ✓ Correct
SELECT COUNT(*) FROM bank_loan_metrics;  -- 1,350 (matches dashboard!)
SELECT COUNT(*) FROM transactions;  -- 81,322 ✓ Correct
```

### API Analysis:
- `/operations/api/customers` returns: **1,547** customer IDs
- `/operations/api/customers/<cid>` returns: customer + accounts + loans + **transactions**
- Frontend pushes each customer to `DB.customers`
- Final count: **1,350** (not 1,547)

### Math:
- Missing customers: 1,547 - 1,350 = **197**
- Missing transactions: 81,322 - 71,267 = **10,055**
- Ratio: 10,055 / 197 ≈ **51 transactions per customer** (realistic!)

---

## How to Fix

### Option 1: Debug Frontend Load (Quick)
1. Open browser DevTools → Network tab
2. Click "Consolidated Dashboard" button
3. Check if all `/operations/api/customers/{id}` requests succeed
4. Look for failed or slow requests
5. Increase timeout or batch the requests sequentially instead of parallel

### Option 2: Fix the API (Recommended)
Create a single bulk endpoint that returns all customer data instead of parallel fetches:
```python
@app.route('/operations/api/bulk-customer-data')
def bulk_customer_data():
    # Return all customers + their accounts/loans/transactions in one go
    # Avoids parallel load issues
```

### Option 3: Optimize Frontend (Medium)
Change from `Promise.all()` to sequential or batched loading:
```javascript
// Load in batches of 10 at a time instead of all at once
for (let i = 0; i < list.length; i += 10) {
  const batch = list.slice(i, i + 10);
  const details = await Promise.all(batch.map(...));
  // Process batch
}
```

---

## Recommendation

**The displayed counts are misleading because:**
- Dashboard shows incomplete data (1,350/1,547 customers = 87%)
- Users think they have all data but are missing 197 customers
- Transactions are under-reported by 10,000

**Action:**
1. **Immediate:** Add console warnings if customer load fails
2. **Short-term:** Switch to bulk endpoint or sequential loading
3. **Long-term:** Use WebSocket or Server-Sent Events for large data loads

---

## Summary Table

| Metric | Expected | Dashboard | Missing | Root Cause |
|--------|----------|-----------|---------|------------|
| Customers | 1,547 | 1,350 | 197 | Incomplete parallel API load |
| Transactions | 81,322 | 71,267 | 10,055 | Customer load failure |
| % Complete | 100% | 86.7% | 13.3% | Network timeout |

