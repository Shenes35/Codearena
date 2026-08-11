/* ════════════════════════════════════════════════════════
   auth.js — Google Sign-In shared module
   Handles Google One Tap + Sign-In button, stores user
   info in localStorage, and exposes helpers used by all pages.
   ════════════════════════════════════════════════════════ */

// ── PASTE YOUR GOOGLE CLIENT ID HERE ──────────────────────
// Get it from: https://console.cloud.google.com
//   → APIs & Services → Credentials → OAuth 2.0 Client ID
const GOOGLE_CLIENT_ID = "1097614216156-pqra9j1mv8hp2d56efut6evnoq9nj1e6.apps.googleusercontent.com";
// ──────────────────────────────────────────────────────────

// ── Admin email — only this account sees the Admin panel ──
const ADMIN_EMAIL = "shenesz13@gmail.com";

function isAdmin() {
  const user = getUser();
  if (user) console.log("[CodeArena] Signed in as:", user.email);
  return user && user.email.toLowerCase() === ADMIN_EMAIL.toLowerCase();
}

const AUTH_KEY = "codearena_user";

/* ── Storage helpers ────────────────────────────────────── */
function getUser() {
  try { return JSON.parse(localStorage.getItem(AUTH_KEY)) || null; }
  catch { return null; }
}

function setUser(userObj) {
  localStorage.setItem(AUTH_KEY, JSON.stringify(userObj));
}

function clearUser() {
  localStorage.removeItem(AUTH_KEY);
}

/* ── Parse Google JWT (id_token) without a library ─────── */
function parseJwt(token) {
  try {
    const base64 = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
    return JSON.parse(atob(base64));
  } catch { return null; }
}

/* ── Called by Google's SDK after sign-in ───────────────── */
function handleGoogleCredential(response) {
  const payload = parseJwt(response.credential);
  if (!payload) return;

  const user = {
    name:    payload.name    || payload.email.split("@")[0],
    email:   payload.email   || "",
    picture: payload.picture || "",
    sub:     payload.sub     || "",           // unique Google user ID
  };
  setUser(user);
  _onSignIn(user);
}
// Expose globally so Google SDK can call it
window.handleGoogleCredential = handleGoogleCredential;

/* ── Internal: actions to run after sign-in ─────────────── */
function _onSignIn(user) {
  _updateNavbar(user);
  _hideSignInModal();
  _updateAdminLink(user);
  // Dispatch custom event for pages that need to react
  window.dispatchEvent(new CustomEvent("codearena:signin", { detail: user }));
}

/* ── Update navbar profile chip ─────────────────────────── */
function _updateNavbar(user) {
  const chip = document.getElementById("auth-chip");
  if (!chip) return;
  if (user) {
    chip.innerHTML = `
      ${user.picture
        ? `<img src="${user.picture}" class="auth-avatar" referrerpolicy="no-referrer" alt="${user.name}" />`
        : `<div class="auth-avatar-placeholder">${user.name.charAt(0).toUpperCase()}</div>`}
      <span class="auth-chip-name">${_escHtml(user.name)}</span>
      <button class="auth-signout-btn" id="btn-signout" title="Sign out">⏻</button>`;
    document.getElementById("btn-signout")?.addEventListener("click", signOut);
  } else {
    chip.innerHTML = `<button class="btn btn-google" id="btn-google-signin">
      <svg width="18" height="18" viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M43.611 20.083H42V20H24v8h11.303c-1.649 4.657-6.08 8-11.303 8-6.627 0-12-5.373-12-12s5.373-12 12-12c3.059 0 5.842 1.154 7.961 3.039l5.657-5.657C34.046 6.053 29.268 4 24 4 12.955 4 4 12.955 4 24s8.955 20 20 20 20-8.955 20-20c0-1.341-.138-2.65-.389-3.917z" fill="#FFC107"/>
        <path d="M6.306 14.691l6.571 4.819C14.655 15.108 18.961 12 24 12c3.059 0 5.842 1.154 7.961 3.039l5.657-5.657C34.046 6.053 29.268 4 24 4 16.318 4 9.656 8.337 6.306 14.691z" fill="#FF3D00"/>
        <path d="M24 44c5.166 0 9.86-1.977 13.409-5.192l-6.19-5.238A11.91 11.91 0 0124 36c-5.202 0-9.619-3.317-11.283-7.946l-6.522 5.025C9.505 39.556 16.227 44 24 44z" fill="#4CAF50"/>
        <path d="M43.611 20.083H42V20H24v8h11.303a12.04 12.04 0 01-4.087 5.571l.003-.002 6.19 5.238C36.971 39.205 44 34 44 24c0-1.341-.138-2.65-.389-3.917z" fill="#1976D2"/>
      </svg>
      Sign in with Google
    </button>`;
    document.getElementById("btn-google-signin")?.addEventListener("click", openSignInModal);
  }
  _updateAdminLink(user);
}

/* ── Show/hide Admin link based on email ─────────────────── */
function _updateAdminLink(user) {
  let adminLink = document.getElementById("admin-nav-link");
  
  if (user && user.email.toLowerCase() === ADMIN_EMAIL.toLowerCase()) {
    if (!adminLink) {
      // Find navbar container to insert Admin link
      const linksContainer = document.querySelector(".navbar-links");
      if (linksContainer) {
        adminLink = document.createElement("a");
        adminLink.className = "nav-link";
        adminLink.id = "admin-nav-link";
        adminLink.href = "admin.html";
        adminLink.textContent = "Admin";
        // Insert right before auth chip or at the end
        const chip = document.getElementById("auth-chip");
        if (chip) {
          linksContainer.insertBefore(adminLink, chip);
        } else {
          linksContainer.appendChild(adminLink);
        }
      }
    } else {
      adminLink.style.display = "";
    }
  } else {
    if (adminLink) {
      adminLink.style.display = "none";
    }
  }
}

/* ── Sign-in modal ───────────────────────────────────────── */
function _ensureModal() {
  if (document.getElementById("google-signin-modal")) return;
  const modal = document.createElement("div");
  modal.id = "google-signin-modal";
  modal.className = "modal-overlay";
  modal.innerHTML = `
    <div class="modal-box signin-modal-box">
      <div class="signin-logo">⚡</div>
      <div class="modal-title">Welcome to CodeArena</div>
      <div class="modal-subtitle">Sign in with your Google account to track your submissions and solve problems.</div>
      <div id="g_id_signin_container" style="display:flex;justify-content:center;margin:24px 0 8px"></div>
      <p class="signin-hint">Your submissions are saved to Google Drive using your display name.</p>
    </div>`;
  document.body.appendChild(modal);
  modal.addEventListener("click", e => { if (e.target === modal) _hideSignInModal(); });

  // Render Google button inside the modal
  if (window.google?.accounts?.id) {
    google.accounts.id.renderButton(
      document.getElementById("g_id_signin_container"),
      { theme: "filled_black", size: "large", shape: "pill", text: "signin_with", width: 280 }
    );
  }
}

function openSignInModal() {
  _ensureModal();
  document.getElementById("google-signin-modal").classList.add("visible");
}

function _hideSignInModal() {
  document.getElementById("google-signin-modal")?.classList.remove("visible");
}

/* ── Sign out ────────────────────────────────────────────── */
function signOut() {
  clearUser();
  if (window.google?.accounts?.id) {
    google.accounts.id.disableAutoSelect();
  }
  _updateNavbar(null);
  _updateAdminLink(null);
  window.dispatchEvent(new CustomEvent("codearena:signout"));
}

/* ── requireLogin: redirect-or-prompt guard ─────────────── */
function requireLogin() {
  const user = getUser();
  if (!user) {
    openSignInModal();
    return null;
  }
  return user;
}

/* ── Init: called once Google SDK is loaded ──────────────── */
function initGoogleAuth() {
  if (!window.google?.accounts?.id) return;

  google.accounts.id.initialize({
    client_id:              GOOGLE_CLIENT_ID,
    callback:               handleGoogleCredential,
    auto_select:            true,    // One Tap auto-select if previously signed in
    cancel_on_tap_outside:  false,
  });

  const existingUser = getUser();
  if (existingUser) {
    _updateNavbar(existingUser);
  } else {
    // Show One Tap popup
    google.accounts.id.prompt((notification) => {
      if (notification.isNotDisplayed() || notification.isSkippedMoment()) {
        // One Tap not shown — update navbar with sign-in button only
        _updateNavbar(null);
      }
    });
    _updateNavbar(null);
  }
}

/* ── Helpers ─────────────────────────────────────────────── */
function _escHtml(str) {
  return String(str || "")
    .replace(/&/g,"&amp;").replace(/</g,"&lt;")
    .replace(/>/g,"&gt;").replace(/"/g,"&quot;");
}

/* ── Export to global scope ──────────────────────────────── */
window.CA_Auth = { getUser, setUser, clearUser, signOut, requireLogin, openSignInModal, isAdmin };
