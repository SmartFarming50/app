from flask import Flask, render_template, request, jsonify
import mysql.connector
import qrcode
from io import BytesIO
import os
import time
from urllib.parse import urlparse

app = Flask(__name__)

# ---------------- DATABASE CONNECTION (SMART) ----------------
def get_db():
    # Try MYSQL_URL / MYSQL_PUBLIC_URL first
    db_url = os.environ.get("MYSQL_URL") or os.environ.get("MYSQL_PUBLIC_URL")

    if db_url:
        url = urlparse(db_url)
        return mysql.connector.connect(
            host=url.hostname,
            user=url.username,
            password=url.password,
            database=url.path.lstrip("/"),
            port=url.port
        )

    # Fallback to internal vars (if linked)
    for _ in range(5):
        try:
            return mysql.connector.connect(
                host=os.environ["MYSQLHOST"],
                user=os.environ["MYSQLUSER"],
                password=os.environ["MYSQLPASSWORD"],
                database=os.environ["MYSQLDATABASE"],
                port=int(os.environ.get("MYSQLPORT", 3306))
            )
        except Exception as e:
            print("Waiting for DB...", e)
            time.sleep(5)

    raise Exception("MySQL connection failed")

# ---------------- HOME ----------------
@app.route("/")
def home():
    return render_template("home.html")

# ---------------- ADMIN UI ----------------
@app.route("/admin-ui")
def admin_ui():
    return render_template("admin.html")

# ---------------- ADMIN GENERATE ----------------
@app.route("/admin", methods=["POST"])
def admin_generate():
    count = int(request.form.get("count", 1))
    db = get_db()
    cur = db.cursor()

    cur.execute("SELECT IFNULL(MAX(id),0) FROM qr_master")
    last = cur.fetchone()[0]

    for i in range(1, count + 1):
        qr_code = f"RAIL-{last+i}"
        img = qrcode.make(qr_code)
        buf = BytesIO()
        img.save(buf, format="PNG")

        cur.execute(
            "INSERT INTO qr_master (qr_code, qr_image) VALUES (%s,%s)",
            (qr_code, buf.getvalue())
        )

    db.commit()
    cur.close()
    db.close()
    return "QR GENERATED SUCCESSFULLY"

# ---------------- SCAN ----------------
@app.route("/scan")
def scan():
    return render_template("scan.html")

# ---------------- ADD PASSENGER ----------------
@app.route("/add-ui/<qr_code>", methods=["GET", "POST"])
def add_ui(qr_code):
    db = get_db()
    cur = db.cursor(dictionary=True)

    cur.execute("SELECT status FROM qr_master WHERE qr_code=%s", (qr_code,))
    qr = cur.fetchone()

    if not qr:
        return "INVALID QR"

    if qr["status"] == "USED":
        return "QR ALREADY USED"

    if request.method == "POST":
        d = request.form
        cur.execute("""
            INSERT INTO passenger_details
            (qr_code,name,address,phone,father,mother)
            VALUES (%s,%s,%s,%s,%s,%s)
        """, (
            qr_code,
            d["name"],
            d["address"],
            d["phone"],
            d["father"],
            d["mother"]
        ))

        cur.execute(
            "UPDATE qr_master SET status='USED' WHERE qr_code=%s",
            (qr_code,)
        )

        db.commit()
        cur.close()
        db.close()
        return "PASSENGER SAVED"

    cur.close()
    db.close()
    return render_template("add.html", qr_code=qr_code)

# ---------------- START ----------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
