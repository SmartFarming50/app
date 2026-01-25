from flask import Flask, render_template, request,send_file
import mysql.connector
import os
import time
from urllib.parse import urlparse
from datetime import datetime
import qrcode
from io import BytesIO
app = Flask(__name__)

# ---------------- DB CONNECTION ----------------
def get_db():
    db_url = os.environ.get("MYSQL_PUBLIC_URL")
    url = urlparse(db_url)

    for _ in range(5):
        try:
            return mysql.connector.connect(
                host=url.hostname,
                port=url.port,
                user=url.username,
                password=url.password,
                database=url.path.lstrip("/"),
                ssl_disabled=False
            )
        except mysql.connector.Error as e:
            print("Waiting for DB...", e)
            time.sleep(5)

    raise Exception("DB connection failed")

# ---------------- HOME ----------------
@app.route("/")
def home():
    return render_template("home.html")
@app.route("/qr-image/<qr_code>")
def qr_image(qr_code):
    img = qrcode.make(qr_code)
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return send_file(buf, mimetype="image/png")
# ---------------- ADMIN UI ----------------
@app.route("/admin-ui")
def admin_ui():
    return render_template("admin.html")

# ---------------- GENERATE QR ----------------
@app.route("/admin", methods=["POST"])
def admin_generate():
    count = int(request.form.get("count", 1))
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    db = get_db()
    cur = db.cursor()

    cur.execute("SELECT IFNULL(MAX(id), 0) FROM qr_data")
    last_id = cur.fetchone()[0]

    for i in range(1, count + 1):
        qr_code = f"RAIL-{last_id + i}"

        cur.execute("""
            INSERT INTO qr_data (qr_code, status, created_at)
            VALUES (%s, %s, %s)
        """, (
            qr_code,
            "UNUSED",
            now
        ))

    db.commit()
    cur.close()
    db.close()
    return "QR codes generated successfully"

# ---------------- SCAN PAGE ----------------
@app.route("/scan")
def scan():
    return render_template("scan.html")

# ---------------- ADD PASSENGER ----------------
@app.route("/add-ui/<qr_code>", methods=["GET", "POST"])
def add_ui(qr_code):
    db = get_db()
    cur = db.cursor(dictionary=True)

    cur.execute(
        "SELECT * FROM qr_data WHERE qr_code=%s",
        (qr_code,)
    )
    qr = cur.fetchone()

    if not qr:
        return "INVALID QR"

    if qr["status"] == "USED":
        return "QR ALREADY USED"

    if request.method == "POST":
        d = request.form
        filled_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        cur.execute("""
            UPDATE qr_data
            SET name=%s,
                father=%s,
                mother=%s,
                phone=%s,
                address=%s,
                filled_at=%s,
                status=%s
            WHERE qr_code=%s
        """, (
            d.get("name"),
            d.get("father"),
            d.get("mother"),
            d.get("phone"),
            d.get("address"),
            filled_time,
            "USED",
            qr_code
        ))

        db.commit()
        cur.close()
        db.close()
        return "Passenger details saved successfully"

    cur.close()
    db.close()
    return render_template("add.html", qr_code=qr_code)

# ---------------- VIEW DETAILS ----------------
@app.route("/view/<qr_code>")
def view_passenger(qr_code):
    db = get_db()
    cur = db.cursor(dictionary=True)

    cur.execute(
        "SELECT * FROM qr_data WHERE qr_code=%s",
        (qr_code,)
    )
    passenger = cur.fetchone()

    cur.close()
    db.close()

    if not passenger:
        return "No data found"

    return render_template("view.html", passenger=passenger)
@app.route("/add-next")
def add_next():
    db = get_db()
    cur = db.cursor(dictionary=True)

    cur.execute("""
        SELECT qr_code FROM qr_data
        WHERE status IS NULL OR status != 'USED'
        ORDER BY id ASC
        LIMIT 1
    """)
    qr = cur.fetchone()

    cur.close()
    db.close()

    if not qr:
        return "No pending QR available"

    return redirect(f"/add-ui/{qr['qr_code']}")

# ---------------- START APP ----------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

