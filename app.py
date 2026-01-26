from flask import Flask, render_template, request, redirect, send_file
import mysql.connector
import os, time
from urllib.parse import urlparse
from datetime import datetime
import qrcode
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader

app = Flask(__name__)

# --------------------------------------------------
# DATABASE CONNECTION
# --------------------------------------------------
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
                database=url.path.lstrip("/")
            )
        except mysql.connector.Error:
            time.sleep(2)

    raise Exception("DB connection failed")

# --------------------------------------------------
# HOME
# --------------------------------------------------
@app.route("/")
def home():
    return render_template("home.html")

# --------------------------------------------------
# ADMIN – GENERATE QR
# --------------------------------------------------
@app.route("/admin", methods=["POST"])
def admin_generate():
    count = int(request.form.get("count", 1))
    now = datetime.now()

    db = get_db()
    cur = db.cursor()

    cur.execute("SELECT IFNULL(MAX(id),0) FROM qr_data")
    last_id = cur.fetchone()[0]

    for i in range(1, count + 1):
        cur.execute(
            "INSERT INTO qr_data (qr_code,status,created_at) VALUES (%s,'UNUSED',%s)",
            (f"RAIL-{last_id+i}", now)
        )

    db.commit()
    cur.close()
    db.close()

    return "QR codes generated successfully"

# --------------------------------------------------
# ADD PASSENGER (MANUAL QR INPUT)
# --------------------------------------------------
@app.route("/add-ui", methods=["GET", "POST"])
def add_ui():
    if request.method == "POST":
        qr_code = request.form.get("qr_code", "").strip().upper()

        if not qr_code:
            return "QR CODE REQUIRED"

        db = get_db()
        cur = db.cursor(dictionary=True)

        cur.execute("SELECT * FROM qr_data WHERE qr_code=%s", (qr_code,))
        qr = cur.fetchone()

        if not qr:
            return "INVALID QR CODE"

        if qr["status"] == "USED":
            return redirect(f"/view/{qr_code}")

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
            request.form["name"],
            request.form["father"],
            request.form["mother"],
            request.form["phone"],
            request.form["address"],
            datetime.now(),
            qr_code
        ))

        db.commit()
        cur.close()
        db.close()

        return f"Passenger details saved for {qr_code}"

    return render_template("add.html")

# --------------------------------------------------
# VIEW PASSENGER
# --------------------------------------------------
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

# --------------------------------------------------
# DOWNLOAD ALL QR CODES AS PDF
# --------------------------------------------------
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
            y -= qr_size + inch
        if y < 2 * inch:
            pdf.showPage()
            x = 1 * inch
            y = height - 1 * inch

    pdf.save()
    buffer.seek(0)

    return send_file(buffer, as_attachment=True,
                     download_name="all_qr_codes.pdf",
                     mimetype="application/pdf")

# --------------------------------------------------
# QR IMAGE
# --------------------------------------------------
@app.route("/qr-image/<qr_code>")
def qr_image(qr_code):
    qr_url = f"{request.host_url.rstrip('/')}/view/{qr_code}"
    img = qrcode.make(qr_url)
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return send_file(buf, mimetype="image/png")

# --------------------------------------------------
# START
# --------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True)
