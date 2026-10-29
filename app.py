"""Medicine Expiry and Recall Tracking System (Python + Oracle PL/SQL)."""
import os
import oracledb
from dotenv import load_dotenv

load_dotenv()


def get_connection():
    return oracledb.connect(
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        dsn=os.getenv("DB_DSN"),
    )


def show(cur, headers):
    rows = cur.fetchall()
    if not rows:
        print("  (no records)")
        return
    print("  " + " | ".join(headers))
    for r in rows:
        print("  " + " | ".join(str(x) for x in r))


def add_medicine(conn):
    name = input("Medicine name: ")
    maker = input("Manufacturer: ")
    cat = input("Category: ")
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO medicines (name, manufacturer, category) VALUES (:1,:2,:3)",
            [name, maker, cat],
        )
    conn.commit()
    print("Medicine added.")


def add_batch(conn):
    med_id = int(input("Medicine ID: "))
    batch_no = input("Batch no: ")
    mfg = input("Mfg date (YYYY-MM-DD): ")
    exp = input("Expiry date (YYYY-MM-DD): ")
    qty = int(input("Quantity: "))
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO batches (medicine_id, batch_no, mfg_date, expiry_date, quantity)
               VALUES (:1,:2,TO_DATE(:3,'YYYY-MM-DD'),TO_DATE(:4,'YYYY-MM-DD'),:5)""",
            [med_id, batch_no, mfg, exp, qty],
        )
    conn.commit()
    print("Batch added (trigger logged the opening stock).")


def stock_move(conn):
    batch_id = int(input("Batch ID: "))
    mtype = input("Type (IN/OUT): ").upper()
    qty = int(input("Quantity: "))
    remarks = input("Remarks: ")
    with conn.cursor() as cur:
        cur.callproc("proc_stock_movement", [batch_id, mtype, qty, remarks])
    conn.commit()
    print("Stock updated.")



def near_expiry(conn):
    days = int(input("Show batches expiring within how many days? [30]: ") or 30)

    with conn.cursor() as cur:
        ref = cur.var(oracledb.DB_TYPE_CURSOR)

        cur.execute(
            "BEGIN :rc := get_near_expiry(:days); END;",
            rc=ref,
            days=days
        )

        result = ref.getvalue()
        print("\nNear-expiry / expired batches")
        show(result, ["ID", "Batch", "Medicine", "Expiry", "Qty", "Days left"])
        result.close()



def run_expiry_job(conn):
    """Runs the PL/SQL cursor procedure and prints its DBMS_OUTPUT."""
    days = int(input("Days window [30]: ") or 30)
    with conn.cursor() as cur:
        cur.callproc("DBMS_OUTPUT.ENABLE", [None])
        cur.callproc("proc_near_expiry_report", [days])
        line = cur.var(str)
        status = cur.var(int)
        while True:
            cur.callproc("DBMS_OUTPUT.GET_LINE", (line, status))
            if status.getvalue() != 0:
                break
            print("  " + line.getvalue())
    conn.commit()


def recall(conn):
    batch_id = int(input("Batch ID to recall: "))
    reason = input("Reason: ")
    with conn.cursor() as cur:
        cur.callproc("process_batch_recall", [batch_id, reason])
    conn.commit()
    print("Batch recalled.")


def view_batches(conn):
    with conn.cursor() as cur:
        cur.execute(
            """SELECT b.batch_id, m.name, b.batch_no, TO_CHAR(b.expiry_date,'YYYY-MM-DD'),
                      b.quantity, b.status
               FROM batches b JOIN medicines m ON m.medicine_id = b.medicine_id
               ORDER BY b.batch_id"""
        )
        show(cur, ["ID", "Medicine", "Batch", "Expiry", "Qty", "Status"])


def view_audit(conn):
    with conn.cursor() as cur:
        cur.execute(
            """SELECT audit_id, batch_id, old_qty, new_qty, action, changed_by,
                      TO_CHAR(changed_on,'YYYY-MM-DD HH24:MI:SS')
               FROM stock_audit ORDER BY audit_id DESC FETCH FIRST 20 ROWS ONLY"""
        )
        show(cur, ["Audit", "Batch", "Old", "New", "Action", "By", "When"])


def view_recalls(conn):
    with conn.cursor() as cur:
        cur.execute(
            """SELECT r.recall_id, b.batch_no, r.qty_recalled, r.reason,
                      TO_CHAR(r.recall_date,'YYYY-MM-DD')
               FROM recalls r JOIN batches b ON b.batch_id = r.batch_id
               ORDER BY r.recall_id"""
        )
        show(cur, ["ID", "Batch", "Qty", "Reason", "Date"])


MENU = {
    "1": ("Add medicine", add_medicine),
    "2": ("Add batch", add_batch),
    "3": ("Stock IN / OUT", stock_move),
    "4": ("View near-expiry batches (REF CURSOR)", near_expiry),
    "5": ("Run expiry job (PL/SQL cursor procedure)", run_expiry_job),
    "6": ("Recall a batch", recall),
    "7": ("View all batches", view_batches),
    "8": ("View stock audit log (trigger)", view_audit),
    "9": ("View recalls", view_recalls),
}


def main():
    conn = get_connection()
    print("Connected to Oracle Database")
    try:
        while True:
            print("\n=== Medicine Expiry & Recall Tracker ===")
            for k, (label, _) in MENU.items():
                print(f"{k}. {label}")
            print("0. Exit")
            choice = input("Choice: ").strip()
            if choice == "0":
                break
            if choice in MENU:
                try:
                    MENU[choice][1](conn)
                except oracledb.DatabaseError as e:
                    conn.rollback()
                    print("Database error:", e)
                except ValueError:
                    print("Invalid input.")
            else:
                print("Invalid choice.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
