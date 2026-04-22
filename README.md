# GreenField Arena · Full-Stack (Flask + MySQL + Static Frontend)

This bundle merges your original HTML/CSS/JS frontend with a Flask + MySQL backend.
The frontend code (in `static/`) is **unchanged** — its `Store` object now talks to
the Flask `/api/*` routes instead of localStorage.

## Project Structure
```
turf-fullstack/
├── app.py                  # Flask routes (auth, slots, bookings, admin)
├── seed_admin.py           # Sets admin password hash (admin123)
├── requirements.txt
├── .env.example
├── sql/
│   └── schema.sql          # Tables, triggers, cursors, stored procedures
└── static/                 # Your original frontend
    ├── index.html
    ├── css/styles.css
    ├── js/
    │   ├── app.js          # ← rewired: Store now uses fetch/XHR → /api/*
    │   └── components.js   # unchanged
    └── pages/
        ├── login.html
        ├── book.html
        ├── confirmation.html
        ├── my-bookings.html
        ├── admin-login.html
        └── admin-dashboard.html
```

## Setup
```bash
# 1. Create venv & install
python -m venv venv && source venv/bin/activate     # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 2. Create database (uses root by default; edit creds in .env or shell)
mysql -u root -p < sql/schema.sql

# 3. Set the real admin password hash
python seed_admin.py     # admin@greenfield.com / admin123

# 4. Run
python app.py
# → open http://localhost:5000
```

## Environment
Either `export` these or put them in a `.env` you load:
```
SECRET_KEY=change-me
DB_HOST=localhost
DB_USER=root
DB_PASSWORD=yourpass
DB_NAME=turf_booking
```

## Routes
| URL                       | Serves                              |
|---------------------------|-------------------------------------|
| `/`                       | static/index.html                   |
| `/book`                   | pages/book.html                     |
| `/login`                  | pages/login.html                    |
| `/my-bookings`            | pages/my-bookings.html              |
| `/confirmation?id=…`      | pages/confirmation.html             |
| `/admin/login`            | pages/admin-login.html              |
| `/admin`                  | pages/admin-dashboard.html          |

API: `/api/auth/{signup,login,admin-login,logout,me}`,
`/api/slots?date=`, `/api/bookings`, `/api/bookings/me`,
`/api/bookings/<id>`, `/api/bookings/<id>/cancel`,
`/api/admin/bookings`, `/api/admin/stats`.

## Database highlights
- **Tables**: users, admins, bookings, booking_slots, payments, booking_logs
- **Triggers**:
  - `trg_prevent_double_booking` — `SIGNAL SQLSTATE '45000'` on slot clash
  - `trg_log_booking_insert` / `trg_log_booking_update` — audit trail
- **Stored Procedures**:
  - `BookSlot(...)` — splits CSV, atomic insert, OUT booking id
  - `CancelBooking(...)` — owner/admin check, refund payment
  - `AutoCompleteBookings()` — past upcoming → completed
  - `GetRevenueReport()` — **CURSOR-based** revenue aggregate

## Notes
- The frontend `Store` uses synchronous `XMLHttpRequest` so original pages don't
  need to be rewritten as async. For production, prefer migrating each page to
  `async/await fetch()`.
- Demo credentials: `admin@greenfield.com` / `admin123`
