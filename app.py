from flask import Flask, render_template, request, redirect, send_file
import mysql.connector
import os
import time
from urllib.parse import urlparse
from datetime import datetime
import qrcode
from io import BytesIO
import cv2
import numpy as np
from pyzbar.pyzbar import decode

app = Flask(__name__)

# ---------------- DATABASE CONNECTION ----------------
def get_db():
    db_url = os.environ.get("MYSQL_PUBLIC_URL")
    if not db_url:
        raise Exception("MYSQL_PUBLIC_URL not set")

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

# ---------------- ADMIN PANEL ----------------
@app.route("/admin-ui")
def admin_ui():
    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("SELECT * FROM qr_data ORDER BY id ASC")
    qr_list = cur.fetchall()
    cur.close()
    db.close()
    return render_template("admin.html", qr_list=qr_list)

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

        # Insert QR record into database
        cur.execute("""
            INSERT INTO qr_data (qr_code, status, created_at)
            VALUES (%s, %s, %s)
        """, (qr_code, "UNUSED", now))

    db.commit()
    cur.close()
    db.close()
    return "QR codes generated successfully"

# ---------------- GENERATE QR IMAGE ON THE FLY ----------------
@app.route("/qr-image/<qr_code>")
def qr_image(qr_code):
    img = qrcode.make(qr_code)
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return send_file(buf, mimetype="image/png")

# ---------------- SCAN PAGE ----------------
@app.route("/scan", methods=["GET", "POST"])
def scan():
    if request.method == "POST":
        # Handle uploaded QR image
        file = request.files.get("qr_image")
        if not file:
            return "No file uploaded"

        img_bytes = np.frombuffer(file.read(), np.uint8)
        img = cv2.imdecode(img_bytes, cv2.IMREAD_COLOR)

        decoded_objects = decode(img)
        if not decoded_objects:
            return "No QR code detected in image"

        qr_code = decoded_objects[0].data.decode("utf-8")
        return redirect(f"/add-ui/{qr_code}")

    return render_template("scan.html")

# ---------------- ADD OR VIEW PASSENGER DETAILS ----------------
@app.route("/add-ui/<qr_code>", methods=["GET", "POST"])
def add_ui(qr_code):
    db = get_db()
    cur = db.cursor(dictionary=True)

    # Fetch QR record
    cur.execute("SELECT * FROM qr_data WHERE qr_code=%s", (qr_code,))
    qr = cur.fetchone()
    if not qr:
        cur.close()
        db.close()
        return "INVALID QR"

    if request.method == "POST":
        # Save passenger details
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

    # GET request → show add form or details if already filled
    return render_template("add.html", qr=qr)

# ---------------- VIEW PASSENGER DETAILS ----------------
@app.route("/view/<qr_code>")
def view_passenger(qr_code):
    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("SELECT * FROM qr_data WHERE qr_code=%s", (qr_code,))
    passenger = cur.fetchone()
    cur.close()
    db.close()

    if not passenger:
        return "No data found"

    return render_template("view.html", passenger=passenger)

# ---------------- START APP ----------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
