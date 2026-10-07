const UUID = /^[0-9a-fA-F-]{36}$/;

export function currentRoute() {
  const path = window.location.hash.slice(1) || "/";
  const parts = path.split("/").filter(Boolean);
  if (parts.length === 0) return { name: "overview", title: "Overview" };
  if (parts[0] === "incidents" && parts.length === 1) return { name: "incidents", title: "Incidents" };
  if (parts[0] === "incidents" && parts.length === 2 && UUID.test(parts[1])) {
    return { name: "incident", id: parts[1], title: "Incident details" };
  }
  if (parts[0] === "investigations" && parts.length === 2 && UUID.test(parts[1])) {
    return { name: "investigation", id: parts[1], title: "Investigation" };
  }
  if (parts[0] === "alerts" && parts.length === 1) return { name: "alerts", title: "Alerts" };
  if (parts[0] === "knowledge" && parts.length === 1) return { name: "knowledge", title: "Knowledge" };
  return { name: "notFound", title: "Page not found" };
}

export function navigate(path) {
  window.location.hash = path;
}
