"""Flask front end for the Medicine Expiry and Recall Tracking System."""
import os
import oracledb
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash

load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET", "dev-secret")


def get_conn():
    return oracledb.connect(
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        dsn=os.getenv("DB_DSN"),
    )


def rows_as_dicts(cur):
    cols = [c[0].lower() for c in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def query(sql, params=None):
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(sql, params or [])
        return rows_as_dicts(cur)


def run_db(action, ok_msg):
    """Run action(cursor), commit, and flash a friendly result."""
    try:
        with get_conn() as conn, conn.cursor() as cur:
            action(cur)
            conn.commit()
        flash(ok_msg, "ok")
    except oracledb.DatabaseError as e:
        msg = str(e).split("\n")[0]          # first line holds the ORA- message
        flash(msg.replace("ORA-20001: ", "").replace("ORA-", "ORA-"), "err")
    except ValueError:
        flash("Invalid input.", "err")


# ---------------------------------------------------------------- dashboard

@app.route("/")
def dashboard():
    days = request.args.get("days", 30, type=int)

    stats = query("""
        SELECT COUNT(*) total,
               NVL(SUM(CASE WHEN status='ACTIVE' THEN 1 END),0) active,
               NVL(SUM(CASE WHEN status='RECALLED' THEN 1 END),0) recalled,
               NVL(SUM(CASE WHEN status='EXPIRED' THEN 1 END),0) expired,
               NVL(SUM(CASE WHEN status='ACTIVE' AND quantity > 0
                        AND expiry_date <= TRUNC(SYSDATE) + 30
                        THEN 1 END),0) near
        FROM batches
    """)[0]

    with get_conn() as conn, conn.cursor() as cur:
        ref_var = cur.var(oracledb.DB_TYPE_CURSOR)

        cur.execute(
            "BEGIN :result := get_near_expiry(:days); END;",
            result=ref_var,
            days=days
        )

        ref = ref_var.getvalue()
        cols = [c[0].lower() for c in ref.description]
        near = [dict(zip(cols, row)) for row in ref.fetchall()]
        ref.close()

    return render_template(
        "dashboard.html",
        stats=stats,
        near=near,
        days=days
    )



@app.route("/run-expiry", methods=["POST"])
def run_expiry():
    days = int(request.form.get("days", 30))
    try:
        with get_conn() as conn, conn.cursor() as cur:
            cur.callproc("DBMS_OUTPUT.ENABLE", [None])
            cur.callproc("proc_near_expiry_report", [days])
            line, status, out = cur.var(str), cur.var(int), []
            while True:
                cur.callproc("DBMS_OUTPUT.GET_LINE", (line, status))
                if status.getvalue() != 0:
                    break
                out.append(line.getvalue())
            conn.commit()
        flash(" • ".join(out) or "Nothing to report.", "ok")
    except oracledb.DatabaseError as e:
        flash(str(e).split("\n")[0], "err")
    return redirect(url_for("dashboard", days=days))


# ---------------------------------------------------------------- medicines
@app.route("/medicines", methods=["GET", "POST"])
def medicines():
    if request.method == "POST":
        f = request.form
        run_db(lambda c: c.execute(
            "INSERT INTO medicines (name, manufacturer, category) VALUES (:1,:2,:3)",
            [f["name"], f["manufacturer"], f["category"]]), "Medicine added.")
        return redirect(url_for("medicines"))
    return render_template("medicines.html",
                           meds=query("SELECT * FROM medicines ORDER BY medicine_id"))


# ------------------------------------------------------------------ batches
@app.route("/batches")
def batches():
    rows = query("""
        SELECT b.batch_id, m.name, b.batch_no, TO_CHAR(b.expiry_date,'YYYY-MM-DD') expiry,
               b.expiry_date - TRUNC(SYSDATE) days_left, b.quantity, b.status
        FROM batches b JOIN medicines m ON m.medicine_id = b.medicine_id
        ORDER BY b.expiry_date""")
    meds = query("SELECT medicine_id, name FROM medicines ORDER BY name")
    return render_template("batches.html", batches=rows, meds=meds)


@app.route("/batches/add", methods=["POST"])
def add_batch():
    f = request.form
    run_db(lambda c: c.execute(
        """INSERT INTO batches (medicine_id, batch_no, mfg_date, expiry_date, quantity)
           VALUES (:1,:2,TO_DATE(:3,'YYYY-MM-DD'),TO_DATE(:4,'YYYY-MM-DD'),:5)""",
        [int(f["medicine_id"]), f["batch_no"], f["mfg_date"], f["expiry_date"],
         int(f["quantity"])]), "Batch added.")
    return redirect(url_for("batches"))


@app.route("/batches/<int:batch_id>/move", methods=["POST"])
def move_stock(batch_id):
    f = request.form
    run_db(lambda c: c.callproc("proc_stock_movement",
           [batch_id, f["type"], int(f["qty"]), f.get("remarks", "")]),
           "Stock updated.")
    return redirect(url_for("batches"))


@app.route("/batches/<int:batch_id>/recall", methods=["POST"])
def recall_batch(batch_id):
    reason = request.form.get("reason", "").strip() or "Quality issue"
    run_db(lambda c: c.callproc("process_batch_recall", [batch_id, reason]),
           "Batch recalled.")
    return redirect(url_for("batches"))


# --------------------------------------------------------------------- logs
@app.route("/logs")
def logs():
    audit = query("""SELECT audit_id, batch_id, old_qty, new_qty, action, changed_by,
                            TO_CHAR(changed_on,'YYYY-MM-DD HH24:MI:SS') changed_on
                     FROM stock_audit ORDER BY audit_id DESC FETCH FIRST 30 ROWS ONLY""")
    moves = query("""SELECT s.movement_id, b.batch_no, s.movement_type, s.qty_change, s.remarks,
                            TO_CHAR(s.moved_on,'YYYY-MM-DD HH24:MI') moved_on
                     FROM stock_movements s JOIN batches b ON b.batch_id = s.batch_id
                     ORDER BY s.movement_id DESC FETCH FIRST 30 ROWS ONLY""")
    recalls = query("""SELECT r.recall_id, b.batch_no, r.qty_recalled, r.reason,
                              TO_CHAR(r.recall_date,'YYYY-MM-DD') recall_date
                       FROM recalls r JOIN batches b ON b.batch_id = r.batch_id
                       ORDER BY r.recall_id DESC""")
    return render_template("logs.html", audit=audit, moves=moves, recalls=recalls)


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5001))
    print(f"Starting MedTrack on http://127.0.0.1:{port}")
    app.run(debug=True, port=port)
