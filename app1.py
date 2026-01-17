import datetime
import jwt
from functools import wraps

from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup

# ---------------- CONFIG ----------------
app = Flask(__name__)
app.secret_key = "CHANGE_THIS_SECRET_KEY"  # Replace for production
CORS(app, supports_credentials=True)

JWT_SECRET = "CHANGE_THIS_JWT_SECRET"  # Replace with strong secret
JWT_ALGO = "HS256"
JWT_EXP_SECONDS = 3600  # 1 hour

# ERP URLs
BASE_URL = "https://exams-nnrg.in"
LOGIN_URL = f"{BASE_URL}/Login.aspx"
MAIN_STUD_URL = f"{BASE_URL}/StudentLogin/MainStud.aspx"

# ---------------- ERP SCRAPER ----------------
class BeeSERP:
    def __init__(self):
        self.session = None

    def extract_hidden_fields(self, html):
        """Extract hidden fields from ASP.NET form"""
        soup = BeautifulSoup(html, "html.parser")
        fields = {}
        for f in ["__VIEWSTATE", "__VIEWSTATEGENERATOR", "__EVENTVALIDATION"]:
            el = soup.find("input", {"name": f})
            fields[f] = el["value"] if el and el.get("value") else ""
        return fields

    def login(self, username, password):
        """Login to ERP portal"""
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "Mozilla/5.0"})

        r1 = self.session.get(LOGIN_URL, timeout=10)
        if r1.status_code != 200:
            return False, "Cannot fetch login page"

        hidden = self.extract_hidden_fields(r1.text)

        # Submit username
        r2 = self.session.post(LOGIN_URL, data={
            **hidden,
            "txtUserName": username,
            "btnNext": "Next"
        }, timeout=10)

        hidden = self.extract_hidden_fields(r2.text)

        # Submit password
        r3 = self.session.post(LOGIN_URL, data={
            **hidden,
            "txtPassword": password,
            "btnSubmit": "Submit"
        }, timeout=10)

        if "lblStudentName" in r3.text or "WELCOME" in r3.text:
            return True, r3.text
        return False, "Invalid credentials"

    def fetch_dashboard_html(self):
        """Fetch main dashboard page HTML"""
        if not self.session:
            return None
        r = self.session.get(MAIN_STUD_URL, timeout=10)
        return r.text if r.status_code == 200 else None

    def parse_dashboard(self, html):
        """Parse dashboard HTML to extract daily attendance and subjects"""
        soup = BeautifulSoup(html, "html.parser")
        info = {}

        # Student Name
        name_tag = soup.find("span", id=lambda x: x and "lblStudentName" in x)
        info["student_name"] = name_tag.text.strip() if name_tag else ""

        # Total Attendance %
        perc_tag = soup.find("span", {"id": "ctl00_cpStud_lblTotalPercentage"})
        info["attendance_percentage"] = perc_tag.text.strip() if perc_tag else ""

        # Subjects with daily attendance
        subjects = []
        tbl = soup.find("table", {"id": "ctl00_cpStud_grdSubject"})
        if tbl:
            for row in tbl.find_all("tr")[1:]:
                cols = row.find_all("td")
                if len(cols) >= 6:
                    subjects.append({
                        "subject": cols[1].text.strip(),
                        "faculty": cols[2].text.strip(),
                        "held": cols[3].text.strip(),
                        "attended": cols[4].text.strip(),
                        "percentage": cols[5].text.strip()
                    })
        info["subjects"] = subjects
        return info

# Initialize ERP scraper
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
    def decorated(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return jsonify({"success": False, "error": "Missing token"}), 401
        token = auth.split(" ")[1]
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
            request.user = payload["username"]
        except jwt.ExpiredSignatureError:
            return jsonify({"success": False, "error": "Token expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"success": False, "error": "Invalid token"}), 401
        return f(*args, **kwargs)
    return decorated

# ---------------- API ENDPOINTS ----------------

@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json()
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    if not username or not password:
        return jsonify({"success": False, "error": "Username and password required"}), 400

    success, result = erp.login(username, password)
    if not success:
        return jsonify({"success": False, "error": result}), 401

    token = create_token(username)
    return jsonify({"success": True, "token": token})

@app.route("/api/dashboard", methods=["GET"])
@token_required
def api_dashboard():
    html = erp.fetch_dashboard_html()
    if not html:
        return jsonify({"success": False, "error": "Failed to fetch dashboard"}), 500
    data = erp.parse_dashboard(html)
    return jsonify({"success": True, "data": data})

@app.route("/api/attendance", methods=["GET"])
@token_required
def api_attendance():
    """Optional endpoint to get only daily attendance per subject"""
    html = erp.fetch_dashboard_html()
    if not html:
        return jsonify({"success": False, "error": "Failed to fetch attendance"}), 500
    data = erp.parse_dashboard(html)
    # return only subject-wise daily attendance
    return jsonify({"success": True, "attendance": data["subjects"]})

# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
