import os
from datetime import date
from functools import wraps

from dotenv import load_dotenv
from flask import Flask, request, jsonify, session, send_from_directory
import mysql.connector
from mysql.connector import pooling
from werkzeug.security import generate_password_hash, check_password_hash
from flask_cors import CORS   # ✅ Added import

load_dotenv()

app = Flask(__name__, static_folder="static", static_url_path="")
app.secret_key = os.environ.get("SECRET_KEY", "change-me-in-prod")

# ✅ Allow only your Vercel frontend domain
CORS(app, origins=["https://turf-booking-system-nu.vercel.app"], supports_credentials=True)

DB_CONFIG = {
    "host": os.environ["DB_HOST"],
    "user": os.environ["DB_USER"],
    "password": os.environ["DB_PASSWORD"],
    "database": os.environ["DB_NAME"],
    "port": int(os.environ.get("DB_PORT", 3306)),
    "autocommit": False,
}

pool = pooling.MySQLConnectionPool(
    pool_name="turf_pool",
    pool_size=5,
    **DB_CONFIG
)

def db():
    return pool.get_connection()

PRICE_PER_HOUR = 800

def _drain_stored_results(cur):
    for rs in cur.stored_results():
        rs.fetchall()

# ---------- AUTH HELPERS ----------
def login_required(f):
    @wraps(f)
    def w(*a, **kw):
        if "user_id" not in session and not session.get("is_admin"):
            return jsonify({"error": "auth required"}), 401
        return f(*a, **kw)
    return w

def admin_required(f):
    @wraps(f)
    def w(*a, **kw):
        if not session.get("is_admin"):
            return jsonify({"error": "admin required"}), 403
        return f(*a, **kw)
    return w

# ---------- STATIC ROUTES ----------
@app.route("/")
def home():
    return send_from_directory(app.static_folder, "index.html")

@app.route("/<page>")
def static_page(page):
    if "." not in page:
        candidate = os.path.join(app.static_folder, "pages", page + ".html")
        if os.path.exists(candidate):
            return send_from_directory(os.path.join(app.static_folder, "pages"), page + ".html")
    return send_from_directory(app.static_folder, page)

@app.route("/admin")
def admin_root():
    return send_from_directory(os.path.join(app.static_folder, "pages"), "admin-dashboard.html")

@app.route("/admin/login")
def admin_login_page_view():
    return send_from_directory(os.path.join(app.static_folder, "pages"), "admin-login.html")

# ---------- AUTH API ----------
@app.post("/api/auth/signup")
def api_signup():
    d = request.get_json(force=True)
    name = (d.get("name") or "").strip()
    email = (d.get("email") or "").strip().lower()
    whatsapp = (d.get("whatsapp") or "").strip()
    password = d.get("password") or ""
    if not name or not email or len(password) < 4:
        return jsonify({"error": "Invalid input"}), 400
    conn = db()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("SELECT id FROM users WHERE email=%s", (email,))
        if cur.fetchone():
            return jsonify({"error": "Email already registered"}), 409
        cur.execute(
            "INSERT INTO users (name, email, whatsapp, password_hash) VALUES (%s, %s, %s, %s)",
            (name, email, whatsapp, generate_password_hash(password))
        )
        conn.commit()
        uid = cur.lastrowid
        user = {"id": uid, "name": name, "email": email, "whatsapp": whatsapp}
        session.clear()
        session["user_id"] = uid
        session["user"] = user
        return jsonify({"user": user})
    finally:
        cur.close()
        conn.close()

@app.post("/api/auth/login")
def api_login():
    d = request.get_json(force=True)
    email = (d.get("email") or "").strip().lower()
    password = d.get("password") or ""
    conn = db()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("SELECT * FROM users WHERE email=%s", (email,))
        u = cur.fetchone()
        if not u or not check_password_hash(u["password_hash"], password):
            return jsonify({"error": "Invalid credentials"}), 401
        user = {"id": u["id"], "name": u["name"], "email": u["email"], "whatsapp": u["whatsapp"]}
        session.clear()
        session["user_id"] = u["id"]
        session["user"] = user
        return jsonify({"user": user})
    finally:
        cur.close()
        conn.close()

@app.post("/api/auth/admin-login")
def api_admin_login():
    d = request.get_json(force=True)
    email = (d.get("email") or "").strip().lower()
    password = d.get("password") or ""
    conn = db()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("SELECT * FROM admins WHERE email=%s", (email,))
        a = cur.fetchone()
        if not a or not check_password_hash(a["password_hash"], password):
            return jsonify({"error": "Invalid admin credentials"}), 401
        session.clear()
        session["admin_id"] = a["id"]
        session["is_admin"] = True
        session["user"] = {"id": "admin", "name": a["name"], "email": a["email"]}
        return jsonify({"ok": True})
    finally:
        cur.close()
        conn.close()

@app.post("/api/auth/logout")
def api_logout():
    session.clear()
    return jsonify({"ok": True})

@app.get("/api/auth/me")
def api_me():
    return jsonify({"user": session.get("user"), "is_admin": session.get("is_admin", False)})

# ---------- (rest of your slots, bookings, admin routes remain unchanged) ----------

# ---------- LOCAL DEVELOPMENT ----------
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
