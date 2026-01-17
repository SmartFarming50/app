import os
import datetime
import jwt
from functools import wraps

from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup

# ---------------- CONFIG ----------------
app = Flask(__name__)

# Secrets from environment variables (IMPORTANT for deployment)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "CHANGE_ME")
JWT_SECRET = os.environ.get("JWT_SECRET_KEY", "CHANGE_ME")

JWT_ALGO = "HS256"
JWT_EXP_SECONDS = 3600  # 1 hour

CORS(app, supports_credentials=True)

# ERP URLs
BASE_URL = "https://exams-nnrg.in"
LOGIN_URL = f"{BASE_URL}/Login.aspx"
MAIN_STUD_URL = f"{BASE_URL}/StudentLogin/MainStud.aspx"

# ---------------- ERP SCRAPER ----------------
class BeeSERP:
    def __init__(self):
        self.session = None

    def extract_hidden_fields(self, html):
        soup = BeautifulSoup(html, "html.parser")
        fields = {}
        for f in ["__VIEWSTATE", "__VIEWSTATEGENERATOR", "__EVENTVALIDATION"]:
            el = soup.find("input", {"name": f})
            fields[f] = el["value"] if el and el.get("value") else ""
        return fields

    def login(self, username, password):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0"
        })

        r1 = self.session.get(LOGIN_URL, timeout=15)
        if r1.status_code != 200:
            return False, "Login page unreachable"

        hidden = self.extract_hidden_fields(r1.text)

        r2 = self.session.post(LOGIN_URL, data={
            **hidden,
            "txtUserName": username,
            "btnNext": "Next"
        }, timeout=15)

        hidden = self.extract_hidden_fields(r2.text)

        r3 = self.session.post(LOGIN_URL, data={
            **hidden,
            "txtPassword": password,
            "btnSubmit": "Submit"
        }, timeout=15)

        if "lblStudentName" in r3.text or "WELCOME" in r3.text:
            return True, "Login successful"

        return False, "Invalid credentials"

    def fetch_dashboard_html(self):
        if not self.session:
            return None
        r = self.session.get(MAIN_STUD_URL, timeout=15)
        return r.text if r.status_code == 200 else None

    def parse_dashboard(self, html):
        soup = BeautifulSoup(html, "html.parser")
        data = {}

        name_tag = soup.find("span", id=lambda x: x and "lblStudentName" in x)
        data["student_name"] = name_tag.text.strip() if name_tag else ""

        perc_tag = soup.find("span", id="ctl00_cpStud_lblTotalPercentage")
        data["attendance_percentage"] = perc_tag.text.strip() if perc_tag else ""

        subjects = []
        table = soup.find("table", id="ctl00_cpStud_grdSubject")
        if table:
            for row in table.find_all("tr")[1:]:
                cols = row.find_all("td")
                if len(cols) >= 6:
                    subjects.append({
                        "subject": cols[1].text.strip(),
                        "faculty": cols[2].text.strip(),
                        "held": cols[3].text.strip(),
                        "attended": cols[4].text.strip(),
                        "percentage": cols[5].text.strip()
                    })

        data["subjects"] = subjects
        return data

erp = BeeSERP()

# ---------------- JWT HELPERS ----------------
def create_token(username):
    payload = {
        "username": username,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(seconds=JWT_EXP_SECONDS)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)

def token_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return jsonify({"success": False, "error": "Token missing"}), 401

        token = auth.split(" ")[1]
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
            request.user = payload["username"]
        except jwt.ExpiredSignatureError:
            return jsonify({"success": False, "error": "Token expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"success": False, "error": "Invalid token"}), 401

        return f(*args, **kwargs)
    return wrapper

# ---------------- API ROUTES ----------------
@app.route("/api/login", methods=["POST"])
def login_api():
    data = request.get_json(force=True)
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()

    if not username or not password:
        return jsonify({"success": False, "error": "Username and password required"}), 400

    success, msg = erp.login(username, password)
    if not success:
        return jsonify({"success": False, "error": msg}), 401

    token = create_token(username)
    return jsonify({"success": True, "token": token})

@app.route("/api/dashboard", methods=["GET"])
@token_required
def dashboard_api():
    html = erp.fetch_dashboard_html()
    if not html:
        return jsonify({"success": False, "error": "Dashboard fetch failed"}), 500

    return jsonify({
        "success": True,
        "data": erp.parse_dashboard(html)
    })

@app.route("/api/attendance", methods=["GET"])
@token_required
def attendance_api():
    html = erp.fetch_dashboard_html()
    if not html:
        return jsonify({"success": False, "error": "Attendance fetch failed"}), 500

    data = erp.parse_dashboard(html)
    return jsonify({"success": True, "attendance": data["subjects"]})

# ---------------- ENTRY ----------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
