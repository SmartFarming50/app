from flask import Flask, render_template, request, jsonify
import mysql.connector
import qrcode
from io import BytesIO
import os
import time

app = Flask(__name__)

# ---------- DATABASE CONNECTION (RAILWAY INTERNAL) ----------
def get_db():
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
    raise Exception("Database not reachable")

# ---------- HOME ----------
@app.route("/")
def home():
    return "<h1>Railway QR System is RUNNING ✅</h1>"

# ---------- ADMIN : GENERATE QR ----------
@app.route("/admin", methods=["POST"])
def admin():
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

# ---------- ADD PASSENGER ----------
@app.route("/add/<qr_code>", methods=["POST"])
def add(qr_code):
    data = request.json
    db = get_db()
    cur = db.cursor()

    cur.execute("SELECT status FROM qr_master WHERE qr_code=%s", (qr_code,))
    row = cur.fetchone()

    if not row:
        return "INVALID QR", 400
    if row[0] == "USED":
        return "QR ALREADY USED", 400

    cur.execute("""
        INSERT INTO passenger_details
        (qr_code,name,address,phone,father,mother)
        VALUES (%s,%s,%s,%s,%s,%s)
    """, (
        qr_code,
        data["name"],
        data["address"],
        data["phone"],
        data["father"],
        data["mother"]
    ))

    cur.execute(
        "UPDATE qr_master SET status='USED' WHERE qr_code=%s",
        (qr_code,)
    )

    db.commit()
    cur.close()
    db.close()
    return "PASSENGER SAVED"

# ---------- FETCH ----------
@app.route("/fetch/<qr_code>")
def fetch(qr_code):
    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute(
        "SELECT * FROM passenger_details WHERE qr_code=%s",
        (qr_code,)
    )
    data = cur.fetchone()
    cur.close()
    db.close()
    return jsonify(data)

# ---------- START SERVER ----------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3000))
    app.run(host="0.0.0.0", port=port)
