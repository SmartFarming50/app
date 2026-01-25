from flask import Flask, render_template, request, jsonify
import mysql.connector
import qrcode
from io import BytesIO
import os
import time

app = Flask(__name__)

# -------------------------------------------------
# DATABASE CONNECTION (RAILWAY INTERNAL NETWORK)
# -------------------------------------------------
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
            print("Waiting for MySQL...", e)
            time.sleep(5)
    raise Exception("MySQL connection failed")

# -------------------------------------------------
# HOME
# -------------------------------------------------
@app.route("/")
def home():
    return render_template("home.html")

# -------------------------------------------------
# ADMIN UI
# -------------------------------------------------
@app.route("/admin-ui")
def admin_ui():
    return render_template("admin.html")

# -------------------------------------------------
# ADMIN API : GENERATE QR CODES
# -------------------------------------------------
@app.route("/admin", methods=["POST"])
def admin_generate():
    count = int(request.form.get("count", 1))

    db = get_db()
    cur = db.cursor()

    cur.execute("SELECT IFNULL(MAX(id), 0) FROM qr_master")
    last_id = cur.fetchone()[0]

    for i in range(1, count + 1):
        qr_code = f"RAIL-{last_id + i}"

        qr_img = qrcode.make(qr_code)
        buf = BytesIO()
        qr_img.save(buf, format="PNG")

        cur.execute(
            "INSERT INTO qr_master (qr_code, qr_image) VALUES (%s, %s)",
            (qr_code, buf.getvalue())
        )

    db.commit()
    cur.close()
    db.close()

    return "<h3>QR Codes Generated Successfully ✅</h3><a href='/'>Home</a>"

# -------------------------------------------------
# SCAN UI
# -------------------------------------------------
@app.route("/scan")
def scan():
    return render_template("scan.html")

# -------------------------------------------------
# ADD PASSENGER UI + SAVE
# -------------------------------------------------
@app.route("/add-ui/<qr_code>", methods=["GET", "POST"])
def add_ui(qr_code):
    db = get_db()
    cur = db.cursor(dictionary=True)

    # Check QR validity
    cur.execute("SELECT status FROM qr_master WHERE qr_code=%s", (qr_code,))
    qr = cur.fetchone()

    if not qr:
        cur.close()
        db.close()
        return "❌ Invalid QR Code"

    if qr["status"] == "USED":
        cur.close()
        db.close()
        return "⚠️ QR Code Already Used"

    if request.method == "POST":
        data = request.form

        cur.execute("""
            INSERT INTO passenger_details
            (qr_code, name, address, phone, father, mother)
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

        return "<h3>Passenger Saved Successfully ✅</h3><a href='/'>Home</a>"

    cur.close()
    db.close()
    return render_template("add.html", qr_code=qr_code)

# -------------------------------------------------
# OPTIONAL API : FETCH PASSENGER DETAILS
# -------------------------------------------------
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

# -------------------------------------------------
# START APPLICATION (RAILWAY PORT)
# -------------------------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3000))
    app.run(host="0.0.0.0", port=port)
