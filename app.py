from flask import Flask, render_template, request, redirect, send_file
import mysql.connector
import os
import time
from urllib.parse import urlparse
from datetime import datetime
import qrcode
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader

app = Flask(__name__)

# ---------------- DB CONNECTION ----------------
def get_db():
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
                database=url.path.lstrip("/"),
                ssl_disabled=False
            )
        except mysql.connector.Error as e:
            print("Waiting for DB...", e)
            time.sleep(5)
    
    raise Exception("DB connection failed")
@app.route("/admin/download-qr-pdf")
def download_qr_pdf():
    db = get_db()
    cur = db.cursor(dictionary=True)

    cur.execute("SELECT qr_code FROM qr_data ORDER BY id ASC")
    qr_list = cur.fetchall()

    cur.close()
    db.close()

    if not qr_list:
        return "No QR codes found"

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)

    width, height = A4
    x = 1 * inch
    y = height - 1 * inch

    qr_size = 2 * inch
    gap = 0.5 * inch

    for qr in qr_list:
        qr_code = qr["qr_code"]
        qr_url = f"{request.host_url.rstrip('/')}/view/{qr_code}"

        qr_img = qrcode.make(qr_url)
        img_buffer = BytesIO()
        qr_img.save(img_buffer, format="PNG")
        img_buffer.seek(0)

        image = ImageReader(img_buffer)
        pdf.drawImage(image, x, y - qr_size, qr_size, qr_size)
        pdf.drawString(x, y - qr_size - 15, qr_code)

        x += qr_size + gap

        if x + qr_size > width:
            x = 1 * inch
            y -= qr_size + 1 * inch

        if y < 2 * inch:
            pdf.showPage()
            x = 1 * inch
            y = height - 1 * inch

    pdf.save()
    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name="all_qr_codes.pdf",
        mimetype="application/pdf"
    )
# ---------------- HOME PAGE ----------------
@app.route("/")
def home():
    return render_template("home.html")
@app.route("/add-ui/<qr_code>", methods=["GET", "POST"])
def add_ui(qr_code):
    db = get_db()
    cur = db.cursor(dictionary=True)

    # Check if QR exists
    cur.execute("SELECT * FROM qr_data WHERE qr_code=%s", (qr_code,))
    qr = cur.fetchone()

    if not qr:
        cur.close()
        db.close()
        return "INVALID QR CODE"

    # If already used → redirect to view
    if qr["status"] == "USED":
        cur.close()
        db.close()
        return redirect(f"/view/{qr_code}")

    if request.method == "POST":
        filled_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        cur.execute("""
            UPDATE qr_data
            SET name=%s,
                father=%s,
                mother=%s,
                phone=%s,
                address=%s,
                filled_at=%s,
                status='USED'
            WHERE qr_code=%s
        """, (
            request.form.get("name"),
            request.form.get("father"),
            request.form.get("mother"),
            request.form.get("phone"),
            request.form.get("address"),
            filled_time,
            qr_code
        ))

        db.commit()
        cur.close()
        db.close()

        return f"Passenger details saved successfully for {qr_code}"

    cur.close()
    db.close()
    return render_template("add.html", qr_code=qr_code)

# ---------------- ADMIN PANEL ----------------
@app.route("/admin-ui")
def admin_ui():
    db = get_db()
    cur = db.cursor(dictionary=True)

    # Fetch all QR codes
    cur.execute("SELECT * FROM qr_data ORDER BY id ASC")
    qr_list = cur.fetchall()

    cur.close()
    db.close()

    return render_template("admin.html", qr_list=qr_list)


# ---------------- GENERATE QR CODES ----------------
@app.route("/admin", methods=["POST"])
def admin_generate():
    count = int(request.form.get("count", 1))
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    db = get_db()
    cur = db.cursor()

    # Get last id
    cur.execute("SELECT IFNULL(MAX(id), 0) FROM qr_data")
    last_id = cur.fetchone()[0]

    for i in range(1, count + 1):
        qr_code = f"RAIL-{last_id + i}"
        cur.execute("""
            INSERT INTO qr_data (qr_code, status, created_at)
            VALUES (%s, %s, %s)
        """, (qr_code, "UNUSED", now))

    db.commit()
    cur.close()
    db.close()

    return f"{count} QR codes generated successfully"

# ---------------- ADD NEXT UNUSED QR ----------------

# ---------------- ADD / FILL PASSENGER DETAILS ----------------
@app.route("/add-ui", methods=["GET", "POST"])
def add_ui():
    if request.method == "POST":
        qr_code = request.form.get("qr_code").strip()

        db = get_db()
        cur = db.cursor(dictionary=True)

        # Check if QR exists
        cur.execute("SELECT * FROM qr_data WHERE qr_code=%s", (qr_code,))
        qr = cur.fetchone()

        if not qr:
            cur.close()
            db.close()
            return "INVALID QR CODE"

        if qr["status"] == "USED":
            cur.close()
            db.close()
            return redirect(f"/view/{qr_code}")

        filled_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        cur.execute("""
            UPDATE qr_data
            SET name=%s,
                father=%s,
                mother=%s,
                phone=%s,
                address=%s,
                filled_at=%s,
                status='USED'
            WHERE qr_code=%s
        """, (
            request.form.get("name"),
            request.form.get("father"),
            request.form.get("mother"),
            request.form.get("phone"),
            request.form.get("address"),
            filled_time,
            qr_code
        ))

        db.commit()
        cur.close()
        db.close()

        return f"Passenger details saved successfully for {qr_code}"

    return render_template("add.html")


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
        return "No data found for this QR"

    return render_template("view.html", passenger=passenger)

# ---------------- SCAN PAGE ----------------
@app.route("/scan")
def scan():
    return render_template("scan.html")

# ---------------- GENERATE QR IMAGE FROM TEXT ----------------
@app.route("/qr-image/<qr_code>")
def qr_image(qr_code):
    qr_url = f"https://app-production-cf67.up.railway.app/view/{qr_code}"

    img = qrcode.make(qr_url)
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return send_file(buf, mimetype="image/png")


# ---------------- START APP ----------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)








