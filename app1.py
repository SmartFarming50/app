from flask import Flask, render_template, request, redirect, jsonify
import mysql.connector
from io import BytesIO
import qrcode
import os

app = Flask(__name__)
QR_FOLDER = "static/qrs"
os.makedirs(QR_FOLDER, exist_ok=True)

# ---------------- CONNECT TO RAILWAY MYSQL ----------------
db = mysql.connector.connect(
    host=os.environ.get("DB_HOST"),
    user=os.environ.get("DB_USER"),
    password=os.environ.get("DB_PASS"),
    database=os.environ.get("DB_NAME")
)
cursor = db.cursor(dictionary=True)

# ---------------- HOME ----------------
@app.route("/")
def home():
    return render_template("home.html")

# ---------------- ADMIN: GENERATE QR ----------------
@app.route("/admin", methods=["GET", "POST"])
def admin():
    if request.method == "POST":
        count = int(request.form["count"])

        # Get last ID
        cursor.execute("SELECT MAX(id) as maxid FROM qr_master")
        last = cursor.fetchone()["maxid"] or 0

        for i in range(1, count+1):
            qr_code = f"RAIL-{last+i}"

            # Generate QR image
            qr = qrcode.make(qr_code)
            buffer = BytesIO()
            qr.save(buffer, format="PNG")
            qr_image = buffer.getvalue()

            # Insert into DB
            cursor.execute(
                "INSERT INTO qr_master (qr_code, qr_image) VALUES (%s,%s)",
                (qr_code, qr_image)
            )

        db.commit()
        return f"{count} QR(s) generated and stored in DB."

    return render_template("admin.html")

# ---------------- SCAN QR ----------------
@app.route("/scan")
def scan():
    return render_template("scan.html")

# ---------------- FETCH PASSENGER DETAILS ----------------
@app.route("/fetch/<qr_code>")
def fetch(qr_code):
    cursor.execute(
        "SELECT * FROM passenger_details WHERE qr_code=%s",
        (qr_code,)
    )
    data = cursor.fetchone()
    return jsonify(data)

# ---------------- ADD PASSENGER DETAILS ----------------
@app.route("/add/<qr_code>", methods=["GET", "POST"])
def add(qr_code):
    # Check QR exists and unused
    cursor.execute("SELECT status FROM qr_master WHERE qr_code=%s", (qr_code,))
    qr = cursor.fetchone()

    if not qr:
        return "Invalid QR Code"
    if qr["status"] == "USED":
        return "QR Code Already Used"

    if request.method == "POST":
        data = request.form
        cursor.execute("""
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

        cursor.execute(
            "UPDATE qr_master SET status='USED' WHERE qr_code=%s",
            (qr_code,)
        )

        db.commit()
        return "Passenger data saved successfully!"

    return render_template("add.html", qr_code=qr_code)

# ---------------- RUN APP ----------------
if __name__ == "__main__":
    # For Railway deployment, use port environment variable
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
