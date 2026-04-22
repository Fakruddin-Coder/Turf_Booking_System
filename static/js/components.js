/* ===== Shared UI helpers (used by page inline scripts) ===== */
function qs(name) {
  return new URLSearchParams(window.location.search).get(name) || "";
}

function toast(message, type) {
  const root = document.getElementById("toast-root");
  if (!root) return;
  const el = document.createElement("div");
  el.className = "toast" + (type ? " " + type : "");
  el.textContent = message;
  root.appendChild(el);
  setTimeout(() => el.remove(), 3500);
}

/** Today's date as YYYY-MM-DD (local timezone). */
function todayIso() {
  const d = new Date();
  const z = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${z(d.getMonth() + 1)}-${z(d.getDate())}`;
}

/** Pretty-print a YYYY-MM-DD or ISO date string for UI. */
function fmtDate(iso) {
  if (!iso) return "—";
  const part = String(iso).slice(0, 10);
  const [y, m, day] = part.split("-").map(Number);
  if (!y || !m || !day) return String(iso);
  const dt = new Date(y, m - 1, day);
  return dt.toLocaleDateString(undefined, {
    weekday: "short",
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

/* ===== Navbar + Footer (injected on every page) ===== */
function pathPrefix() {
  return location.pathname.includes("/pages/") ? "../" : "";
}
function renderNavbar() {
  const root = document.getElementById("navbar"); if (!root) return;
  const p = pathPrefix();
  const s = Store.get();
  const userPart = s.user
    ? `<a href="${p}pages/my-bookings.html">My Bookings</a>
       <a href="${p}pages/profile.html">Profile</a>
       <button type="button" class="btn btn-ghost" id="logout-btn"><strong>Logout</strong></button>`
    : `<a href="${p}pages/login.html">Login</a>
       <a href="${p}pages/book.html" class="btn btn-primary">Book Now</a>`;
  const adminLink = s.isAdmin
    ? `<a href="${p}pages/admin-dashboard.html">Admin</a>`
    : `<a href="${p}pages/admin-login.html" style="font-size:.85rem;color:var(--text-muted)">Admin</a>`;
  root.innerHTML = `
    <nav class="nav">
      <div class="container nav-inner">
        <a href="${p}index.html" class="brand">
          <span class="brand-logo">⚽</span> Greenfield Arena
        </a>
        <button class="nav-burger" aria-label="Menu">☰</button>
        <div class="nav-links">
          <a href="${p}index.html">Home</a>
          <a href="${p}pages/book.html">Book</a>
          ${adminLink}
          ${userPart}
        </div>
      </div>
    </nav>`;
  const burger = root.querySelector(".nav-burger");
  const links = root.querySelector(".nav-links");
  burger.addEventListener("click", () => links.classList.toggle("open"));
  const lo = root.querySelector("#logout-btn");
  if (lo) lo.addEventListener("click", () => { Store.logout(); toast("Logged out"); setTimeout(() => location.href = p + "index.html", 400); });
}

function renderFooter() {
  const root = document.getElementById("footer"); if (!root) return;
  const p = pathPrefix();
  root.innerHTML = `
    <footer>
      <div class="container">
        <div>
          <div class="brand" style="color:white;margin-bottom:.5rem"><span class="brand-logo">⚽</span> Greenfield Arena</div>
          <p style="color:rgba(255,255,255,0.6);font-size:.9rem">Premium 5-a-side football turf. Andheri West, Mumbai.</p>
        </div>
        <div>
          <h4>Quick Links</h4>
          <a href="${p}index.html">Home</a>
          <a href="${p}pages/book.html">Book a Slot</a>
          <a href="${p}pages/my-bookings.html">My Bookings</a>
          <a href="${p}pages/profile.html">Profile</a>
        </div>
        <div>
          <h4>Contact</h4>
          <a href="tel:+912200000000">+91 22 0000 0000</a>
          <a href="mailto:hello@greenfield.com">hello@greenfield.com</a>
          <a href="https://wa.me/919800000000" target="_blank">WhatsApp us</a>
        </div>
      </div>
      <div class="footer-bottom">© ${new Date().getFullYear()} Greenfield Arena. All rights reserved.</div>
    </footer>`;
}

document.addEventListener("DOMContentLoaded", () => {
  renderNavbar();
  renderFooter();
  Store.refreshStatuses();
});
