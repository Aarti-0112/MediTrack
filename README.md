# Medicine Expiry and Recall Tracking System
Python (oracledb, Flask) + Oracle PL/SQL

## Setup
1. Run in order on your Oracle DB (FreeSQL): 01_schema.sql, 02_plsql.sql (each block up to `/`), 03_sample_data.sql
2. Copy `.env.example` to `.env` and fill in DB_USER, DB_PASSWORD, DB_DSN, FLASK_SECRET
3. `pip install -r requirements.txt`
4. Web UI: `python web_app.py` -> http://127.0.0.1:5000
   Command-line menu: `python app.py`

## PL/SQL objects
- proc_near_expiry_report : explicit cursor, near-expiry batches (marks expired)
- get_near_expiry         : same query as REF CURSOR for Python
- proc_stock_movement     : stock IN/OUT
- process_batch_recall    : batch recall
- trg_batch_stock_audit   : trigger logging every stock change
