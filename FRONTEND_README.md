# Greenfield Arena — Frontend (HTML/CSS/JS)

Pure static frontend for a turf booking site. **No build step, no framework.**
Uses `localStorage` for demo state — swap with your Flask/MySQL API later.

## Run

```bash
cd turf-frontend
python3 -m http.server 8000
# open http://localhost:8000
```

Or just double-click `index.html`.

## Pages

- `index.html` — Home (hero, facilities, pricing, CTA)
- `pages/book.html` — Slot picker (Morning/Afternoon/Evening/Night), real-time availability, summary
- `pages/login.html` — User login + signup (toggle)
- `pages/admin-login.html` — Admin login (`admin@greenfield.com` / `admin123`)
- `pages/confirmation.html` — QR code, booking ID, WhatsApp share, print ticket
- `pages/my-bookings.html` — Upcoming / Completed / Cancelled tabs
- `pages/admin-dashboard.html` — Stats, filters, cancel bookings

## Connecting to Flask

Replace `Store.*` calls in `js/app.js` with `fetch()` calls to your Flask routes:

| Demo function | Replace with |
|---|---|
| `Store.login(email, pass)` | `POST /api/login` |
| `Store.signup(...)` | `POST /api/signup` |
| `Store.adminLogin(...)` | `POST /api/admin/login` |
| `Store.createBooking(...)` | `POST /api/bookings` |
| `Store.cancelBooking(id)` | `POST /api/bookings/{id}/cancel` |
| `Store.isSlotBooked(date, slot)` | `GET /api/slots?date=...` |
| `Store.get().bookings` (admin) | `GET /api/admin/bookings` |

## Tech

- Vanilla HTML / CSS / JS (no build)
- Google Fonts (Inter + Poppins)
- QRCode.js (CDN) for confirmation QR
- Sporty & energetic green gradient theme, mobile-first
