import { clearToken, hasToken, onAuthFailure, request, setToken } from "./api.js";
import { currentRoute, navigate } from "./router.js";
import { renderRoute, showError } from "./views.js";

const root = document.getElementById("content");
const authScreen = document.getElementById("auth-screen");
const authForm = document.getElementById("auth-form");
const authInput = document.getElementById("token-input");
const authError = document.getElementById("auth-error");
const authSubmit = document.getElementById("auth-submit");
const connectionLabel = document.getElementById("connection-label");
const connectionStatus = connectionLabel.parentElement;
const toastElement = document.getElementById("toast");
let activeController = null;
let toastTimer = null;

function toast(message, error = false) {
  toastElement.textContent = message;
  toastElement.classList.toggle("error", error);
  toastElement.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { toastElement.hidden = true; }, 4500);
}

function lock(message = "") {
  activeController?.abort();
  clearToken();
  authInput.value = "";
  root.replaceChildren();
  authScreen.hidden = false;
  authError.textContent = message;
  connectionLabel.textContent = "Session locked";
  connectionStatus.classList.remove("connected");
  document.getElementById("last-updated").textContent = "Not loaded";
  authInput.focus();
}

function setNavigation(route) {
  const section = route.name === "incident" || route.name === "investigation" ? "incidents" : route.name;
  for (const link of document.querySelectorAll("[data-nav]")) {
    const selected = link.dataset.nav === section;
    link.classList.toggle("active", selected);
    if (selected) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  }
  document.getElementById("breadcrumb-current").textContent = route.title;
  document.title = `${route.title} · Vigilia`;
}

async function renderCurrent() {
  activeController?.abort();
  const controller = new AbortController();
  activeController = controller;
  const route = currentRoute();
  setNavigation(route);
  if (!hasToken()) return;
  root.replaceChildren();
  try {
    await renderRoute(route, {
      root,
      signal: controller.signal,
      toast,
      navigate,
      refresh: renderCurrent,
    });
    if (!controller.signal.aborted) {
      document.getElementById("last-updated").textContent = `Updated ${new Date().toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" })}`;
    }
  } catch (error) {
    if (controller.signal.aborted || error.name === "AbortError" || !hasToken()) return;
    showError(root, error, renderCurrent);
  }
}

onAuthFailure(lock);
authForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const value = authInput.value.trim();
  if (!value) return;
  authSubmit.disabled = true;
  authError.textContent = "";
  setToken(value);
  try {
    await request("/incidents");
    authInput.value = "";
    authScreen.hidden = true;
    connectionLabel.textContent = "Connected to API";
    connectionStatus.classList.add("connected");
    await renderCurrent();
  } catch (error) {
    if (error.code === "api_security_not_configured") authError.textContent = "API security is not configured on the server.";
    else if (error.status !== 401) authError.textContent = error.message;
    if (error.status !== 401) clearToken();
  } finally {
    authSubmit.disabled = false;
  }
});

document.getElementById("lock-button").addEventListener("click", () => lock());
document.getElementById("refresh-button").addEventListener("click", renderCurrent);
window.addEventListener("hashchange", renderCurrent);
setNavigation(currentRoute());
authInput.focus();
