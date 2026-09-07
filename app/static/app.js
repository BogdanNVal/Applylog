"use strict";

const $ = (id) => document.getElementById(id);

const state = {
  authMode: "login",
  editingId: null,
  applications: [],
};


async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });

  if (response.status === 204) return null;

  const body = await response.json().catch(() => null);
  if (!response.ok) {
    throw new Error(readError(body, response.status));
  }
  return body;
}

function readError(body, status) {
  const detail = body && body.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail.length) {
    const first = detail[0];
    const field = (first.loc || []).slice(-1)[0];
    return field ? `${field}: ${first.msg}` : first.msg;
  }
  return `Request failed (${status})`;
}

function toast(message, isError = false) {
  const el = $("toast");
  el.textContent = message;
  el.classList.toggle("is-error", isError);
  el.hidden = false;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => {
    el.hidden = true;
  }, 2600);
}

/* Auth */

function setAuthMode(mode) {
  state.authMode = mode;
  const isLogin = mode === "login";
  $("tab-login").classList.toggle("is-active", isLogin);
  $("tab-register").classList.toggle("is-active", !isLogin);
  $("auth-submit").textContent = isLogin ? "Sign in" : "Create account";
  $("auth-password").autocomplete = isLogin ? "current-password" : "new-password";
  $("auth-error").hidden = true;
}

function showAuthView() {
  $("app-view").hidden = true;
  $("auth-view").hidden = false;
  $("auth-password").value = "";
}

async function showAppView(user) {
  $("auth-view").hidden = true;
  $("app-view").hidden = false;
  $("user-email").textContent = user.email;
  await refresh();
}

async function handleAuthSubmit(event) {
  event.preventDefault();
  const error = $("auth-error");
  error.hidden = true;

  const email = $("auth-email").value.trim();
  const password = $("auth-password").value;
  if (!email || password.length < 8) {
    error.textContent = "Enter an email and a password of at least 8 characters.";
    error.hidden = false;
    return;
  }

  const button = $("auth-submit");
  button.disabled = true;
  try {
    const user = await api(`/api/auth/${state.authMode === "login" ? "login" : "register"}`, {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
    await showAppView(user);
    toast(state.authMode === "login" ? "Welcome back" : "Account created");
  } catch (err) {
    error.textContent = err.message;
    error.hidden = false;
  } finally {
    button.disabled = false;
  }
}

async function logout() {
  await api("/api/auth/logout", { method: "POST" });
  showAuthView();
  toast("Signed out");
}

/* Dashboard */

function filterParams() {
  const params = new URLSearchParams();
  const q = $("filter-q").value.trim();
  if (q) params.set("q", q);
  if ($("filter-status").value) params.set("status", $("filter-status").value);
  if ($("filter-from").value) params.set("from", $("filter-from").value);
  if ($("filter-to").value) params.set("to", $("filter-to").value);
  return params;
}

async function refresh() {
  const query = filterParams().toString();
  const [applications, stats] = await Promise.all([
    api(`/api/applications${query ? `?${query}` : ""}`),
    api("/api/applications/stats"),
  ]);
  state.applications = applications;
  renderStats(stats);
  renderRows(applications);
}

function renderStats(stats) {
  $("stat-total").textContent = stats.total;
  $("stat-applied").textContent = stats.applied;
  $("stat-interview").textContent = stats.interview;
  $("stat-offer").textContent = stats.offer;
  $("stat-response").textContent = `${stats.response_rate}%`;
  $("stat-week").textContent = stats.last_7_days;
}

function formatDate(iso) {
  const parsed = new Date(`${iso}T00:00:00`);
  return Number.isNaN(parsed.getTime())
    ? iso
    : parsed.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
}

function renderRows(applications) {
  const tbody = $("rows");
  tbody.replaceChildren();

  const empty = $("empty-state");
  if (!applications.length) {
    const filtered = filterParams().toString().length > 0;
    empty.textContent = filtered
      ? "No applications match these filters."
      : "No applications yet. Add the first one to start tracking.";
    empty.hidden = false;
    return;
  }
  empty.hidden = true;

  for (const item of applications) {
    const row = document.createElement("tr");
    row.dataset.id = item.id;

    const company = document.createElement("td");
    if (item.link) {
      const anchor = document.createElement("a");
      anchor.className = "company-link";
      anchor.href = item.link;
      anchor.target = "_blank";
      anchor.rel = "noopener noreferrer";
      anchor.textContent = item.company;
      company.append(anchor);
    } else {
      const strong = document.createElement("strong");
      strong.textContent = item.company;
      company.append(strong);
    }
    if (item.location) {
      const sub = document.createElement("span");
      sub.className = "cell-sub";
      sub.textContent = item.location;
      company.append(sub);
    }

    const role = document.createElement("td");
    role.textContent = item.role;
    if (item.notes) {
      const sub = document.createElement("span");
      sub.className = "cell-sub";
      sub.textContent = item.notes.length > 70 ? `${item.notes.slice(0, 70)}...` : item.notes;
      role.append(sub);
    }

    const applied = document.createElement("td");
    applied.textContent = formatDate(item.applied_on);

    const status = document.createElement("td");
    const badge = document.createElement("span");
    badge.className = `badge ${item.status}`;
    badge.textContent = item.status;
    status.append(badge);

    const actions = document.createElement("td");
    actions.className = "col-actions";
    const editBtn = document.createElement("button");
    editBtn.type = "button";
    editBtn.className = "btn-link";
    editBtn.textContent = "Edit";
    editBtn.addEventListener("click", () => openDialog(item));
    const deleteBtn = document.createElement("button");
    deleteBtn.type = "button";
    deleteBtn.className = "btn-link danger";
    deleteBtn.textContent = "Delete";
    deleteBtn.addEventListener("click", () => removeApplication(item));
    actions.append(editBtn, deleteBtn);

    row.append(company, role, applied, status, actions);
    tbody.append(row);
  }
}

/* Form */

function openDialog(item) {
  state.editingId = item ? item.id : null;
  $("dialog-title").textContent = item ? "Edit application" : "Add application";
  $("form-error").hidden = true;
  $("f-company").value = item ? item.company : "";
  $("f-role").value = item ? item.role : "";
  $("f-applied-on").value = item ? item.applied_on : new Date().toISOString().slice(0, 10);
  $("f-status").value = item ? item.status : "applied";
  $("f-location").value = item ? item.location : "";
  $("f-link").value = item ? item.link : "";
  $("f-notes").value = item ? item.notes : "";
  $("app-dialog").showModal();
  $("f-company").focus();
}

async function saveApplication(event) {
  event.preventDefault();
  const error = $("form-error");
  error.hidden = true;

  const payload = {
    company: $("f-company").value.trim(),
    role: $("f-role").value.trim(),
    applied_on: $("f-applied-on").value,
    status: $("f-status").value,
    location: $("f-location").value.trim(),
    link: $("f-link").value.trim(),
    notes: $("f-notes").value.trim(),
  };

  if (!payload.company || !payload.role || !payload.applied_on) {
    error.textContent = "Company, role and applied date are required.";
    error.hidden = false;
    return;
  }

  const button = $("save-btn");
  button.disabled = true;
  try {
    if (state.editingId) {
      await api(`/api/applications/${state.editingId}`, {
        method: "PUT",
        body: JSON.stringify(payload),
      });
    } else {
      await api("/api/applications", { method: "POST", body: JSON.stringify(payload) });
    }
    $("app-dialog").close();
    await refresh();
    toast(state.editingId ? "Application updated" : "Application added");
  } catch (err) {
    error.textContent = err.message;
    error.hidden = false;
  } finally {
    button.disabled = false;
  }
}

async function removeApplication(item) {
  if (!confirm(`Delete the ${item.role} application at ${item.company}?`)) return;
  try {
    await api(`/api/applications/${item.id}`, { method: "DELETE" });
    await refresh();
    toast("Application deleted");
  } catch (err) {
    toast(err.message, true);
  }
}

/* Wiring */

function debounce(fn, delay) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), delay);
  };
}

async function safeRefresh() {
  try {
    await refresh();
  } catch (err) {
    toast(err.message, true);
  }
}

function wireEvents() {
  $("tab-login").addEventListener("click", () => setAuthMode("login"));
  $("tab-register").addEventListener("click", () => setAuthMode("register"));
  $("auth-form").addEventListener("submit", handleAuthSubmit);
  $("logout-btn").addEventListener("click", logout);

  $("filter-q").addEventListener("input", debounce(safeRefresh, 250));
  for (const id of ["filter-status", "filter-from", "filter-to"]) {
    $(id).addEventListener("change", safeRefresh);
  }
  $("clear-filters").addEventListener("click", () => {
    $("filter-q").value = "";
    $("filter-status").value = "";
    $("filter-from").value = "";
    $("filter-to").value = "";
    safeRefresh();
  });

  $("export-btn").addEventListener("click", () => {
    const query = filterParams().toString();
    window.location.href = `/api/applications/export.csv${query ? `?${query}` : ""}`;
  });

  $("new-btn").addEventListener("click", () => openDialog(null));
  $("cancel-btn").addEventListener("click", () => $("app-dialog").close());
  $("app-form").addEventListener("submit", saveApplication);
}

async function start() {
  wireEvents();
  setAuthMode("login");
  try {
    const user = await api("/api/auth/me");
    await showAppView(user);
  } catch {
    showAuthView();
  }
}

start();
