/* ============================================================
   Greenfield Arena – Front-end Store wired to Flask /api/*
   Keeps the SAME synchronous Store API the original pages used,
   by hydrating a local cache from the server on each page load
   via one blocking XHR (small payload, runs once per nav).
   ============================================================ */
const PRICE_PER_HOUR = 800;
const TURF = { name: "Greenfield Arena", location: "Andheri West, Mumbai" };

const ALL_SLOTS = [];
for (let h = 6; h < 23; h++) {
  const start = String(h).padStart(2, "0") + ":00";
  const end   = String(h + 1).padStart(2, "0") + ":00";
  let period = "Morning";
  if (h >= 12 && h < 16) period = "Afternoon";
  else if (h >= 16 && h < 20) period = "Evening";
  else if (h >= 20) period = "Night";
  ALL_SLOTS.push({ id: `${start}-${end}`, start, end, period });
}
const SLOTS_BY_PERIOD = ALL_SLOTS.reduce((acc, s) => {
  (acc[s.period] = acc[s.period] || []).push(s); return acc;
}, {});

// ---- tiny sync XHR helper (runs once on each page load) ----
function syncGET(url) {
  const x = new XMLHttpRequest();
  x.open("GET", url, false);            // sync
  try { x.send(null); } catch { return null; }
  if (x.status >= 200 && x.status < 300) { try { return JSON.parse(x.responseText); } catch { return null; } }
  return null;
}
async function asyncPOST(url, data) {
  const r = await fetch(url, { method: "POST", headers: {"Content-Type":"application/json"}, body: JSON.stringify(data||{}) });
  let body=null; try{ body = await r.json(); }catch{}
  return { ok: r.ok, status: r.status, body: body || {} };
}
async function asyncGET(url) {
  const r = await fetch(url); let body=null; try{ body=await r.json(); }catch{}
  return { ok: r.ok, status: r.status, body: body || {} };
}

/** Parse Flask JSON `{ error: "..." }` and map HTTP status to a clear booking message. */
function xhrBookingErrorMessage(xhr, fallback) {
  let fromBody = "";
  try {
    const t = (xhr.responseText || "").trim();
    if (t) {
      const j = JSON.parse(t);
      if (j && j.error) fromBody = String(j.error);
    }
  } catch (_) { /* non-JSON body */ }
  const s = xhr.status;
  if (s === 0) return "Network error. Check your connection and try again.";
  if (s === 401) return "Session expired. Please log in again.";
  if (s === 403) return fromBody || "Customer login is required to book (for example, log out of admin if you are in the admin account).";
  if (s === 400) return fromBody || "Invalid booking details. Check name, WhatsApp, date, and slots.";
  if (s === 409) return fromBody || "That slot is no longer available. Refresh and pick another time.";
  if (s >= 500) return fromBody || "Server error. Please try again in a moment.";
  return fromBody || fallback;
}

// ---- bootstrap the cached snapshot used by sync Store.get() ----
let _snapshot = { user: null, isAdmin: false, bookings: [] };
function _bootstrap() {
  const me = syncGET("/api/auth/me");
  if (me && me.user) { _snapshot.user = me.user; _snapshot.isAdmin = !!me.is_admin; }
  // Load relevant bookings: admin sees all, user sees their own
  if (_snapshot.isAdmin) {
    const r = syncGET("/api/admin/bookings?status=all");
    if (r && r.bookings) _snapshot.bookings = r.bookings;
  } else if (_snapshot.user) {
    const r = syncGET("/api/bookings/me");
    if (r && r.bookings) _snapshot.bookings = r.bookings;
  }
}
_bootstrap();

const Store = {
  get() { return _snapshot; },

  // refreshStatuses() is server-side via AutoCompleteBookings; just re-bootstrap
  refreshStatuses() { _bootstrap(); },

  // Used by Book page to gray out booked slots. Synchronous — uses /api/slots once per page render.
  // Cache by date so we don't re-call repeatedly inside the same render pass.
  _slotCache: {},
  _ensureSlotsForDate(date) {
    if (!this._slotCache[date]) {
      const r = syncGET("/api/slots?date=" + encodeURIComponent(date));
      this._slotCache[date] = r && r.booked ? new Set(r.booked) : new Set();
    }
    return this._slotCache[date];
  },
  isSlotBooked(date, slotId) { return this._ensureSlotsForDate(date).has(slotId); },

  // ---- Auth ----
  login(email, password) {
    // sync XHR for unchanged page code paths
    const x = new XMLHttpRequest();
    x.open("POST","/api/auth/login",false);
    x.setRequestHeader("Content-Type","application/json");
    try { x.send(JSON.stringify({email,password})); } catch { return {ok:false,error:"Network error"}; }
    if (x.status===200) { _bootstrap(); return { ok:true }; }
    try { return { ok:false, error: JSON.parse(x.responseText).error || "Login failed" }; }
    catch { return { ok:false, error:"Login failed" }; }
  },
  signup(name, email, password) {
    const x = new XMLHttpRequest();
    x.open("POST","/api/auth/signup",false);
    x.setRequestHeader("Content-Type","application/json");
    try { x.send(JSON.stringify({name,email,password})); } catch { return {ok:false,error:"Network error"}; }
    if (x.status===200) { _bootstrap(); return { ok:true }; }
    try { return { ok:false, error: JSON.parse(x.responseText).error || "Signup failed" }; }
    catch { return { ok:false, error:"Signup failed" }; }
  },
  adminLogin(email, password) {
    const x = new XMLHttpRequest();
    x.open("POST","/api/auth/admin-login",false);
    x.setRequestHeader("Content-Type","application/json");
    try { x.send(JSON.stringify({email,password})); } catch { return {ok:false,error:"Network error"}; }
    if (x.status===200) { _bootstrap(); return { ok:true }; }
    try { return { ok:false, error: JSON.parse(x.responseText).error || "Login failed" }; }
    catch { return { ok:false, error:"Use admin@greenfield.com / admin123" }; }
  },
  logout() {
    const x = new XMLHttpRequest();
    x.open("POST","/api/auth/logout",false); try{x.send(null);}catch{}
    _snapshot = { user:null, isAdmin:false, bookings:[] };
  },

  // ---- Bookings ----
  createBooking(input) {
    if (!_snapshot.user) return { error: "Please login first" };
    const x = new XMLHttpRequest();
    x.open("POST","/api/bookings",false);
    x.setRequestHeader("Content-Type","application/json");
    try { x.send(JSON.stringify(input)); } catch { return { error:"Network error" }; }
    if (x.status===200) {
      const b = JSON.parse(x.responseText);
      _snapshot.bookings = [b, ..._snapshot.bookings];
      // invalidate slot cache for that date
      delete this._slotCache[input.date];
      return b;
    }
    return { error: xhrBookingErrorMessage(x, "Booking failed") };
  },
  cancelBooking(id) {
    const x = new XMLHttpRequest();
    x.open("POST","/api/bookings/"+encodeURIComponent(id)+"/cancel",false);
    try { x.send(null); } catch { return; }
    if (x.status===200) {
      _snapshot.bookings = _snapshot.bookings.map(b => b.id===id ? {...b, status:"cancelled"} : b);
    }
  },
};

window.Store = Store;
window.PRICE_PER_HOUR = PRICE_PER_HOUR;
window.TURF = TURF;
window.ALL_SLOTS = ALL_SLOTS;
window.SLOTS_BY_PERIOD = SLOTS_BY_PERIOD;
