# app.py
from flask import Flask, render_template, request, redirect, url_for
import mysql.connector
from io import BytesIO
import qrcode
import os
import time
from urllib.parse import urlparse

app = Flask(__name__)

# ---------------- DATABASE CONNECTION ----------------
def get_db():
    """Connect to Railway MySQL using public URL (hopper proxy)."""
    db_url = os.environ.get("MYSQL_PUBLIC_URL")
    if not db_url:
        raise Exception("MYSQL_PUBLIC_URL environment variable not set")
    
    url = urlparse(db_url)
    for _ in range(5):
        try:
            return mysql.connector.connect(
                host=url.hostname,
                port=url.port,
                user=url.username,
                password=url.password,
                database=url.path.lstrip("/")
            )
        except mysql.connector.Error as e:
            print("Waiting for DB...", e)
            time.sleep(5)
    raise Exception("Could not connect to MySQL database")

# ---------------- HOME ----------------
@app.route("/")
def home():
    return render_template("home.html")

# ---------------- ADMIN UI ----------------
@app.route("/admin-ui")
def admin_ui():
    return render_template("admin.html")

# ---------------- ADMIN GENERATE QRs ----------------
@app.route("/admin", methods=["POST"])
def admin_generate():
    count = int(request.form.get("count", 1))
    db = get_db()
    cur = db.cursor()

    # Get last QR ID
    cur.execute("SELECT IFNULL(MAX(id), 0) FROM qr_master")
    last_id = cur.fetchone()[0]

    for i in range(1, count + 1):
        qr_code = f"RAIL-{last_id + i}"
        img = qrcode.make(qr_code)
        buf = BytesIO()
        img.save(buf, format="PNG")
        
        # Insert into qr_master
        cur.execute(
            "INSERT INTO qr_master (qr_code, qr_image) VALUES (%s,%s)",
            (qr_code, buf.getvalue())
        )

    db.commit()
    cur.close()
    db.close()
    return f"{count} QR(s) generated successfully!"

# ---------------- SCAN UI ----------------
@app.route("/scan")
def scan():
    return render_template("scan.html")

# ---------------- ADD PASSENGER DETAILS ----------------
@app.route("/add-ui/<qr_code>", methods=["GET", "POST"])
def add_ui(qr_code):
    db = get_db()
    cur = db.cursor(dictionary=True)

    # Check QR exists and unused
    cur.execute("SELECT status FROM qr_master WHERE qr_code=%s", (qr_code,))
    qr = cur.fetchone()
    if not qr:
        cur.close()
        db.close()
        return "INVALID QR"

    if qr["status"] == "USED":
        cur.close()
        db.close()
        return "QR ALREADY USED"

    if request.method == "POST":
        d = request.form
        cur.execute("""
            INSERT INTO passenger_details
            (qr_code, name, address, phone, father, mother)
            VALUES (%s,%s,%s,%s,%s,%s)
        """, (
            qr_code,
            d.get("name"),
            d.get("address"),
            d.get("phone"),
            d.get("father"),
            d.get("mother")
        ))

        # Update QR status
        cur.execute("UPDATE qr_master SET status='USED' WHERE qr_code=%s", (qr_code,))
        db.commit()
        cur.close()
        db.close()
        return "Passenger saved successfully!"

    cur.close()
    db.close()
    return render_template("add.html", qr_code=qr_code)

# ---------------- VIEW PASSENGER BY QR ----------------
@app.route("/view/<qr_code>")
def view_passenger(qr_code):
    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("SELECT * FROM passenger_details WHERE qr_code=%s", (qr_code,))
    passenger = cur.fetchone()
    cur.close()
    db.close()
    if not passenger:
        return "No passenger found"
    return render_template("view.html", passenger=passenger)

# ---------------- START APP ----------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
