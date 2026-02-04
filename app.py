import os
from flask import Flask, render_template_string

app = Flask(__name__)

@app.route("/")
def payment_success():
    return render_template_string("""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Payment Successful</title>
    <style>
        body {
            margin: 0;
            font-family: 'Segoe UI', Tahoma, sans-serif;
            background: linear-gradient(135deg, #43cea2, #185a9d);
            height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }

        .card {
            background: white;
            width: 380px;
            padding: 40px;
            border-radius: 18px;
            text-align: center;
            box-shadow: 0 20px 45px rgba(0,0,0,0.25);
        }

        .check {
            width: 80px;
            height: 80px;
            margin: auto;
            background: #4CAF50;
            border-radius: 50%;
            color: white;
            font-size: 42px;
            display: flex;
            align-items: center;
            justify-content: center;
            margin-bottom: 20px;
        }

        h1 {
            color: #333;
            margin-bottom: 8px;
        }

        p {
            color: #666;
            margin-bottom: 25px;
        }

        .info {
            background: #f2f2f2;
            padding: 14px;
            border-radius: 8px;
            font-size: 14px;
            margin-bottom: 25px;
        }

        .btn {
            padding: 12px 28px;
            background: #185a9d;
            color: white;
            text-decoration: none;
            border-radius: 25px;
            transition: 0.3s;
        }

        .btn:hover {
            background: #144a82;
        }
    </style>
</head>
<body>

<div class="card">
    <div class="check">✓</div>
    <h1>Payment Successful</h1>
    <p>Your payment has been processed successfully.</p>

    <div class="info">
        <strong>Amount:</strong> $99.00<br>
        <strong>Status:</strong> Completed
    </div>

    <a class="btn" href="#">Continue</a>
</div>

</body>
</html>
""")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
