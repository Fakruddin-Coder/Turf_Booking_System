"""
GreenField Arena – Combined Flask + MySQL backend
serving the original static HTML/CSS/JS frontend from /static.
Run:  pip install -r requirements.txt
      mysql -u root -p < sql/schema.sql
      python seed_admin.py
      python app.py        # http://localhost:5000
"""
import os
from dotenv import load_dotenv  # 1. Import the loader
from datetime import datetime, date
from functools import wraps
# ... other imports ...

load_dotenv() # 2. THIS IS THE KEY: It pulls the password from your .env file
import os
from datetime import date
from functools import wraps
from flask import Flask, request, jsonify, session, send_from_directory, redirect
import mysql.connector
from mysql.connector import pooling
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__, static_folder="static", static_url_path="")
app.secret_key = os.environ.get("SECRET_KEY", "change-me-in-prod")

DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "user": os.environ.get("DB_USER", "root"),
    "password": os.environ.get("DB_PASSWORD", "Khan@123"),
    "database": os.environ.get("DB_NAME", "turf_booking"),
    "autocommit": False,
}
pool = pooling.MySQLConnectionPool(pool_name="turf_pool", pool_size=5, **DB_CONFIG)
def db(): return pool.get_connection()
PRICE_PER_HOUR = 800

def _drain_stored_results(cur):
    """mysql-connector-python requires reading all result sets after callproc() before reusing the cursor."""
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
def home(): return send_from_directory(app.static_folder, "index.html")

@app.route("/<path:page>")
def static_page(page):
    # Allow /book → pages/book.html, /login → pages/login.html, etc.
    if "." not in page:
        candidate = os.path.join(app.static_folder, "pages", page + ".html")
        if os.path.exists(candidate):
            return send_from_directory(os.path.join(app.static_folder, "pages"), page + ".html")
    return send_from_directory(app.static_folder, page)

@app.route("/admin")
def admin_root(): return send_from_directory(os.path.join(app.static_folder, "pages"), "admin-dashboard.html")
@app.route("/admin/login")
def admin_login_page_view(): return send_from_directory(os.path.join(app.static_folder, "pages"), "admin-login.html")

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
    conn = db(); cur = conn.cursor(dictionary=True)
    try:
        cur.execute("SELECT id FROM users WHERE email=%s", (email,))
        if cur.fetchone(): return jsonify({"error": "Email already registered"}), 409
        cur.execute("INSERT INTO users (name,email,whatsapp,password_hash) VALUES (%s,%s,%s,%s)",
                    (name, email, whatsapp, generate_password_hash(password)))
        conn.commit()
        uid = cur.lastrowid
        user = {"id": uid, "name": name, "email": email, "whatsapp": whatsapp}
        session.clear(); session["user_id"] = uid; session["user"] = user
        return jsonify({"user": user})
    finally: cur.close(); conn.close()

@app.post("/api/auth/login")
def api_login():
    d = request.get_json(force=True)
    email = (d.get("email") or "").strip().lower()
    password = d.get("password") or ""
    conn = db(); cur = conn.cursor(dictionary=True)
    try:
        cur.execute("SELECT * FROM users WHERE email=%s", (email,))
        u = cur.fetchone()
        if not u or not check_password_hash(u["password_hash"], password):
            return jsonify({"error": "Invalid credentials"}), 401
        user = {"id": u["id"], "name": u["name"], "email": u["email"], "whatsapp": u["whatsapp"]}
        session.clear(); session["user_id"] = u["id"]; session["user"] = user
        return jsonify({"user": user})
    finally: cur.close(); conn.close()

@app.post("/api/auth/admin-login")
def api_admin_login():
    d = request.get_json(force=True)
    email = (d.get("email") or "").strip().lower()
    password = d.get("password") or ""
    conn = db(); cur = conn.cursor(dictionary=True)
    try:
        cur.execute("SELECT * FROM admins WHERE email=%s", (email,))
        a = cur.fetchone()
        if not a or not check_password_hash(a["password_hash"], password):
            return jsonify({"error": "Invalid admin credentials"}), 401
        session.clear(); session["admin_id"] = a["id"]; session["is_admin"] = True
        session["user"] = {"id": "admin", "name": a["name"], "email": a["email"]}
        return jsonify({"ok": True})
    finally: cur.close(); conn.close()

@app.post("/api/auth/logout")
def api_logout(): session.clear(); return jsonify({"ok": True})

@app.get("/api/auth/me")
def api_me():
    return jsonify({"user": session.get("user"), "is_admin": session.get("is_admin", False)})

# ---------- SLOTS (AJAX) ----------
def _slot_grid():
    periods = [("Morning",6,12),("Afternoon",12,16),("Evening",16,20),("Night",20,23)]
    out = []
    for p,fr,to in periods:
        for h in range(fr,to):
            out.append({"id": f"{h:02d}:00-{h+1:02d}:00", "start": f"{h:02d}:00",
                        "end": f"{h+1:02d}:00", "period": p})
    return out

@app.get("/api/slots")
def api_slots():
    d = request.args.get("date") or date.today().isoformat()
    conn = db(); cur = conn.cursor(dictionary=True)
    try:
        cur.callproc("AutoCompleteBookings"); conn.commit()
        _drain_stored_results(cur)
        cur.execute("SELECT slot_id FROM booking_slots bs "
                    "JOIN bookings b ON b.id=bs.booking_id "
                    "WHERE b.booking_date=%s AND b.status<>'cancelled'", (d,))
        booked = [r["slot_id"] for r in cur.fetchall()]
        return jsonify({"date": d, "price_per_hour": PRICE_PER_HOUR,
                        "slots": _slot_grid(), "booked": booked})
    finally: cur.close(); conn.close()

# ---------- BOOKINGS ----------
@app.post("/api/bookings")
@login_required
def api_create_booking():
    if not session.get("user_id"):
        return jsonify({"error": "Log in with your player account to book (admin session cannot place bookings)."}), 403
    d = request.get_json(force=True)
    name = (d.get("name") or "").strip()
    whatsapp = (d.get("whatsapp") or "").strip()
    bdate = d.get("date")
    slot_ids = d.get("slotIds") or d.get("slot_ids") or []
    payment_method = d.get("paymentMethod") or d.get("payment_method") or "upi"
    if not name or not whatsapp or not bdate or not slot_ids:
        return jsonify({"error": "Missing fields"}), 400
    if bdate < date.today().isoformat():
        return jsonify({"error": "Cannot book past dates"}), 400
    amount = len(slot_ids) * PRICE_PER_HOUR
    conn = db(); cur = conn.cursor()
    try:
        result = cur.callproc("BookSlot",
            [session["user_id"], name, whatsapp, bdate,
             ",".join(slot_ids), amount, payment_method, "0"*20])
        _drain_stored_results(cur)
        new_id = result[7]
        if isinstance(new_id, (bytes, bytearray)):
            new_id = new_id.decode()
        conn.commit()
        return jsonify({"id": new_id, "userId": session["user_id"], "name": name,
                        "whatsapp": whatsapp, "date": bdate, "slotIds": slot_ids,
                        "amount": amount, "status": "upcoming",
                        "paymentMethod": payment_method})
    except mysql.connector.Error as e:
        conn.rollback(); return jsonify({"error": e.msg}), 409
    finally: cur.close(); conn.close()

def _row_to_booking(r, slot_ids):
    return {"id": r["id"], "userId": r["user_id"], "name": r["name"],
            "whatsapp": r["whatsapp"], "date": r["booking_date"].isoformat(),
            "amount": float(r["amount"]), "status": r["status"],
            "paymentMethod": r["payment_method"],
            "createdAt": r["created_at"].isoformat() if r.get("created_at") else None,
            "slotIds": slot_ids}

@app.get("/api/bookings/me")
@login_required
def api_my_bookings():
    conn = db(); cur = conn.cursor(dictionary=True)
    try:
        cur.callproc("AutoCompleteBookings"); conn.commit()
        _drain_stored_results(cur)
        cur.execute("SELECT * FROM bookings WHERE user_id=%s ORDER BY created_at DESC",
                    (session["user_id"],))
        rows = cur.fetchall()
        slots_map = {}
        if rows:
            ids = tuple(r["id"] for r in rows); fmt = ",".join(["%s"]*len(ids))
            cur.execute(f"SELECT booking_id, slot_id FROM booking_slots WHERE booking_id IN ({fmt})", ids)
            for s in cur.fetchall():
                slots_map.setdefault(s["booking_id"], []).append(s["slot_id"])
        return jsonify({"bookings": [_row_to_booking(r, slots_map.get(r["id"], [])) for r in rows]})
    finally: cur.close(); conn.close()

@app.get("/api/bookings/<bid>")
def api_get_booking(bid):
    conn = db(); cur = conn.cursor(dictionary=True)
    try:
        cur.execute("SELECT * FROM bookings WHERE id=%s", (bid,))
        b = cur.fetchone()
        if not b: return jsonify({"error": "Not found"}), 404
        cur.execute("SELECT slot_id FROM booking_slots WHERE booking_id=%s", (bid,))
        slots = [r["slot_id"] for r in cur.fetchall()]
        return jsonify({"booking": _row_to_booking(b, slots)})
    finally: cur.close(); conn.close()

@app.post("/api/bookings/<bid>/cancel")
@login_required
def api_cancel(bid):
    conn = db(); cur = conn.cursor()
    try:
        cur.callproc("CancelBooking", [bid, session.get("user_id") or 0,
                                       1 if session.get("is_admin") else 0])
        _drain_stored_results(cur)
        conn.commit(); return jsonify({"ok": True})
    except mysql.connector.Error as e:
        conn.rollback(); return jsonify({"error": e.msg}), 400
    finally: cur.close(); conn.close()

# ---------- ADMIN ----------
@app.get("/api/admin/bookings")
@admin_required
def api_admin_bookings():
    status = request.args.get("status"); q = request.args.get("q","").strip()
    conn = db(); cur = conn.cursor(dictionary=True)
    try:
        cur.callproc("AutoCompleteBookings"); conn.commit()
        _drain_stored_results(cur)
        sql = "SELECT * FROM bookings WHERE 1=1"; params = []
        if status and status != "all": sql += " AND status=%s"; params.append(status)
        if q:
            sql += " AND (name LIKE %s OR whatsapp LIKE %s OR id LIKE %s)"
            like=f"%{q}%"; params += [like,like,like]
        sql += " ORDER BY created_at DESC LIMIT 500"
        cur.execute(sql, params); rows = cur.fetchall()
        slots_map = {}
        if rows:
            ids = tuple(r["id"] for r in rows); fmt = ",".join(["%s"]*len(ids))
            cur.execute(f"SELECT booking_id, slot_id FROM booking_slots WHERE booking_id IN ({fmt})", ids)
            for s in cur.fetchall():
                slots_map.setdefault(s["booking_id"], []).append(s["slot_id"])
        return jsonify({"bookings": [_row_to_booking(r, slots_map.get(r["id"], [])) for r in rows]})
    finally: cur.close(); conn.close()

@app.get("/api/admin/stats")
@admin_required
def api_admin_stats():
    conn = db(); cur = conn.cursor(dictionary=True)
    try:
        cur.callproc("GetRevenueReport")
        stats = {}
        for r in cur.stored_results():
            row = r.fetchone()
            if row:
                stats = {k: float(v) if hasattr(v,"real") and not isinstance(v,bool) else v
                         for k,v in row.items()}
        return jsonify({"stats": stats})
    finally: cur.close(); conn.close()

if __name__ == "__main__":
    app.run(debug=True, port=5000)
