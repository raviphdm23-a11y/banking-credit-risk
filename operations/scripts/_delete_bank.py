import sqlite3, sys

bid = sys.argv[1] if len(sys.argv) > 1 else 'BANK002'
conn = sqlite3.connect('bank.db')

n = conn.execute('DELETE FROM transactions WHERE bank_id=?', (bid,)).rowcount
print(f'transactions      : deleted {n} rows')

cust_ids = [r[0] for r in conn.execute('SELECT id FROM customers WHERE bank_id=?', (bid,)).fetchall()]
if cust_ids:
    placeholders = ','.join('?' * len(cust_ids))
    n = conn.execute(f'DELETE FROM customer_kyc WHERE cid IN ({placeholders})', cust_ids).rowcount
    print(f'customer_kyc      : deleted {n} rows')

for table in ['accounts', 'loans', 'credit_risk_metrics', 'bank_loan_metrics',
              'customers', 'branches', 'reg_capital_reports', 'reg_liquidity_reports',
              'reg_client_exposures', 'bank_balance_sheet', 'bank_profit_loss']:
    try:
        n = conn.execute(f'DELETE FROM {table} WHERE bank_id=?', (bid,)).rowcount
        print(f'{table:<25}: deleted {n} rows')
    except Exception as e:
        print(f'{table:<25}: {e}')

for table in ['rm_cases', 'rm_case_events', 'rm_outcomes']:
    try:
        n = conn.execute(f'DELETE FROM {table} WHERE bank_id=?', (bid,)).rowcount
        print(f'{table:<25}: deleted {n} rows')
    except Exception:
        pass

conn.commit()
conn.close()
print(f'\nAll data for {bid} deleted. Bank master row kept for upsert.')
