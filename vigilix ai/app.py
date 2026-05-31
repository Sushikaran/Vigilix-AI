import os
import sqlite3
from datetime import datetime
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, session, flash, Response, send_file
from werkzeug.security import generate_password_hash, check_password_hash

from config import SECRET_KEY
from utils.database import init_db, get_db
from utils.detector import HybridDetector
from utils.streamer import generate_frames

app = Flask(__name__)
app.secret_key = SECRET_KEY

os.makedirs("evidence", exist_ok=True)
os.makedirs("models", exist_ok=True)

detector = HybridDetector()


def login_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return func(*args, **kwargs)
    return wrapper


def build_monthly_stats(user_id):
    conn = get_db()
    rows = conn.execute(
        """
        SELECT substr(alert_date, 1, 7) AS month, COUNT(*) AS count
        FROM alerts
        WHERE user_id = ? AND alert_date IS NOT NULL
        GROUP BY month
        ORDER BY month DESC
        LIMIT 6
        """,
        (user_id,)
    ).fetchall()
    conn.close()

    data = list(reversed([dict(r) for r in rows]))
    if not data:
        data = [
            {"month": "Jan", "count": 0},
            {"month": "Feb", "count": 0},
            {"month": "Mar", "count": 0},
            {"month": "Apr", "count": 0},
            {"month": "May", "count": 0},
            {"month": "Jun", "count": 0},
        ]
    max_count = max([d["count"] for d in data] + [1])
    for d in data:
        d["height"] = 12 + int((d["count"] / max_count) * 88) if max_count else 12
    return data


@app.route("/")
def home():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return render_template("home.html")


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        gmail = request.form.get("gmail", "").strip().lower()
        password = request.form.get("password", "")

        if not username or not gmail or not password:
            flash("Username, Gmail and password are required.", "error")
            return redirect(url_for("signup"))

        conn = get_db()
        try:
            conn.execute(
                "INSERT INTO users (username, gmail, password, created_at) VALUES (?, ?, ?, ?)",
                (username, gmail, generate_password_hash(password), datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            )
            conn.commit()
            flash("Account created successfully. Please login.", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("Username or Gmail already exists.", "error")
        finally:
            conn.close()

    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        conn.close()

        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["gmail"] = user["gmail"]
            return redirect(url_for("dashboard"))

        flash("Invalid username or password.", "error")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))


@app.route("/dashboard")
@login_required
def dashboard():
    today = datetime.now().strftime("%Y-%m-%d")
    user_id = session["user_id"]
    conn = get_db()
    cameras = conn.execute("SELECT * FROM cameras WHERE user_id = ? ORDER BY id DESC", (user_id,)).fetchall()
    alerts = conn.execute(
        """
        SELECT alerts.*, cameras.camera_name, cameras.location, cameras.location_type
        FROM alerts
        LEFT JOIN cameras ON alerts.camera_id = cameras.id
        WHERE alerts.user_id = ?
        ORDER BY alerts.id DESC
        LIMIT 8
        """,
        (user_id,)
    ).fetchall()
    total_alerts = conn.execute("SELECT COUNT(*) AS c FROM alerts WHERE user_id = ?", (user_id,)).fetchone()["c"]
    today_alerts = conn.execute("SELECT COUNT(*) AS c FROM alerts WHERE user_id = ? AND alert_date = ?", (user_id, today)).fetchone()["c"]
    evidence_count = conn.execute("SELECT COUNT(*) AS c FROM alerts WHERE user_id = ? AND evidence_path != ''", (user_id,)).fetchone()["c"]
    conn.close()
    return render_template("dashboard.html", cameras=cameras, alerts=alerts, total_alerts=total_alerts, today_alerts=today_alerts, evidence_count=evidence_count, monthly_stats=build_monthly_stats(user_id))


@app.route("/add_camera", methods=["GET", "POST"])
@login_required
def add_camera():
    if request.method == "POST":
        camera_name = request.form.get("camera_name", "").strip()
        location = request.form.get("location", "").strip()
        location_type = request.form.get("location_type", "School").strip()
        source = request.form.get("source", "").strip()
        alert_email = request.form.get("alert_email", "").strip()
        if not camera_name or not location or not source:
            flash("Camera name, location and camera source are required.", "error")
            return redirect(url_for("add_camera"))
        conn = get_db()
        conn.execute(
            """
            INSERT INTO cameras (user_id, camera_name, location, location_type, source, alert_email, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (session["user_id"], camera_name, location, location_type, source, alert_email, "Active", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )
        conn.commit()
        conn.close()
        flash("Camera added successfully.", "success")
        return redirect(url_for("dashboard"))
    return render_template("add_camera.html")


@app.route("/camera/<int:camera_id>")
@login_required
def camera_view(camera_id):
    conn = get_db()
    camera = conn.execute("SELECT * FROM cameras WHERE id = ? AND user_id = ?", (camera_id, session["user_id"])).fetchone()
    conn.close()
    if not camera:
        return "Camera not found", 404
    return render_template("camera_view.html", camera=camera)


@app.route("/delete_camera/<int:camera_id>")
@login_required
def delete_camera(camera_id):
    conn = get_db()
    conn.execute("DELETE FROM cameras WHERE id = ? AND user_id = ?", (camera_id, session["user_id"]))
    conn.commit()
    conn.close()
    flash("Camera removed.", "success")
    return redirect(url_for("dashboard"))


@app.route("/video_feed/<int:camera_id>")
@login_required
def video_feed(camera_id):
    conn = get_db()
    camera = conn.execute("SELECT * FROM cameras WHERE id = ? AND user_id = ?", (camera_id, session["user_id"])).fetchone()
    conn.close()
    if not camera:
        return "Camera not found", 404
    return Response(generate_frames(camera, detector), mimetype="multipart/x-mixed-replace; boundary=frame")


@app.route("/alerts")
@login_required
def alerts():
    conn = get_db()
    rows = conn.execute(
        """
        SELECT alerts.*, cameras.camera_name, cameras.location, cameras.location_type
        FROM alerts
        LEFT JOIN cameras ON alerts.camera_id = cameras.id
        WHERE alerts.user_id = ?
        ORDER BY alerts.id DESC
        """,
        (session["user_id"],)
    ).fetchall()
    conn.close()
    return render_template("alerts.html", alerts=rows)


@app.route("/analytics")
@login_required
def analytics():
    user_id = session["user_id"]
    conn = get_db()
    location_rows = conn.execute(
        """
        SELECT cameras.location_type, COUNT(alerts.id) AS count
        FROM cameras
        LEFT JOIN alerts ON cameras.id = alerts.camera_id
        WHERE cameras.user_id = ?
        GROUP BY cameras.location_type
        ORDER BY count DESC
        """,
        (user_id,)
    ).fetchall()
    type_rows = conn.execute(
        """
        SELECT threat_type, COUNT(*) AS count
        FROM alerts
        WHERE user_id = ?
        GROUP BY threat_type
        ORDER BY count DESC
        LIMIT 10
        """,
        (user_id,)
    ).fetchall()
    conn.close()
    return render_template("analytics.html", monthly_stats=build_monthly_stats(user_id), location_rows=location_rows, type_rows=type_rows)


@app.route("/evidence/<path:filename>")
@login_required
def evidence(filename):
    return send_file(os.path.join("evidence", filename))


@app.route("/clear_alerts")
@login_required
def clear_alerts():
    conn = get_db()
    conn.execute("DELETE FROM alerts WHERE user_id = ?", (session["user_id"],))
    conn.commit()
    conn.close()
    flash("Alert history cleared.", "success")
    return redirect(url_for("alerts"))


@app.route("/usage")
@login_required
def usage():
    return render_template("usage.html")


@app.route("/data_info")
@login_required
def data_info():
    return render_template("data_info.html")


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True, use_reloader=False)
