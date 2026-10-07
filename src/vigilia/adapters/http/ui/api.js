let token = null;
let authFailureHandler = () => {};

export class ApiError extends Error {
  constructor(status, code, message, metadata = {}) {
    super(message);
    this.status = status;
    this.code = code;
    this.metadata = metadata;
  }
}

export function setToken(value) { token = value; }
export function clearToken() { token = null; }
export function hasToken() { return Boolean(token); }
export function onAuthFailure(handler) { authFailureHandler = handler; }

export async function request(path, { method = "GET", body, headers = {}, signal } = {}) {
  const requestHeaders = { Authorization: `Bearer ${token}`, ...headers };
  if (body !== undefined) requestHeaders["Content-Type"] = "application/json";
  let response;
  try {
    response = await fetch(path, {
      method,
      headers: requestHeaders,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal,
      cache: "no-store",
    });
  } catch (error) {
    if (error.name === "AbortError") throw error;
    throw new ApiError(0, "network_error", "Could not connect to Vigilia. Check that the API is running.");
  }
  if (response.status === 204) return null;
  let payload;
  try {
    payload = await response.json();
  } catch {
    throw new ApiError(response.status, "invalid_response", "The API returned an invalid response.");
  }
  if (!response.ok) {
    const error = payload?.error || {};
    if (response.status === 401) {
      clearToken();
      authFailureHandler("The API token was rejected. Please enter it again.");
    }
    throw new ApiError(response.status, error.code || "request_failed", error.message || "The request failed.", error.metadata || {});
  }
  return payload;
}
