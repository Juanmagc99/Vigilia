import { request } from "./api.js";

function el(tag, className = "", text = null) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== null && text !== undefined) node.textContent = String(text);
  return node;
}

function append(parent, ...children) {
  for (const child of children) if (child) parent.append(child);
  return parent;
}

function link(text, href, className = "text-link") {
  const node = el("a", className, text);
  node.href = `/ui/#${href}`;
  return node;
}

function button(text, className = "button") {
  const node = el("button", className, text);
  node.type = "button";
  return node;
}

function badge(value) {
  const safe = String(value || "unknown").toLowerCase().replace(/[^a-z_]/g, "");
  return el("span", `badge badge-${safe}`, String(value || "unknown").replaceAll("_", " "));
}

function utcTimestamp(value) {
  // Legacy alert/incident columns return UTC timestamps without an offset.
  return /(?:Z|[+-]\d{2}:\d{2})$/i.test(value) ? value : `${value}Z`;
}

function dateTime(value) {
  if (!value) return "—";
  const date = new Date(utcTimestamp(value));
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" });
}

function timeNode(value) {
  const node = el("time", "", dateTime(value));
  if (value) {
    node.dateTime = utcTimestamp(value);
    node.title = `${node.dateTime} · shown in your local time zone`;
  }
  return node;
}

function heading(kicker, title, description, action = null) {
  const header = el("div", "page-head");
  const copy = el("div");
  append(copy, el("p", "eyebrow", kicker), el("h1", "", title), el("p", "subtitle", description));
  append(header, copy, action);
  return header;
}

function panel(title, body = null, action = null) {
  const wrapper = el("section", "panel");
  append(wrapper, append(el("div", "panel-header"), el("h2", "", title), action));
  if (body) wrapper.append(body);
  return wrapper;
}

function empty(title, description) {
  return append(el("div", "empty"), el("strong", "", title), el("p", "", description));
}

function loading(root) {
  root.replaceChildren(el("div", "loading", "Loading data…"));
}

export function showError(root, error, retry) {
  const wrapper = el("div", "error-panel");
  const action = button("Try again");
  action.addEventListener("click", retry);
  append(wrapper, el("strong", "", "Unable to load this view"), el("p", "", error.message || "The request failed."), action);
  root.replaceChildren(wrapper);
}

function keyValues(entries) {
  const list = el("dl", "key-value");
  for (const [name, value] of entries) append(list, el("dt", "", name), el("dd", "", value ?? "—"));
  return list;
}

function externalLink(label, rawUrl) {
  if (!rawUrl) return null;
  try {
    const url = new URL(rawUrl);
    if (url.protocol !== "http:" && url.protocol !== "https:") return null;
    const node = el("a", "text-link", `${label} ↗`);
    node.href = url.href;
    node.target = "_blank";
    node.rel = "noopener noreferrer";
    return node;
  } catch {
    return null;
  }
}

function labels(values) {
  const group = el("div", "label-list");
  for (const [name, value] of Object.entries(values || {})) group.append(el("span", "label-chip", `${name}: ${value}`));
  if (!group.childElementCount) group.append(el("span", "muted", "None"));
  return group;
}

function alertDetails(alert) {
  const details = el("details");
  details.append(el("summary", "details-toggle", "View event details"));
  const body = el("div", "details-content");
  append(body, keyValues([
    ["Fingerprint", alert.fingerprint],
    ["Source", alert.source],
    ["Started", dateTime(alert.starts_at)],
    ["Ended", dateTime(alert.ends_at)],
    ["Description", alert.description],
  ]));
  append(body, el("h3", "", "Labels"), labels(alert.labels), el("h3", "", "Annotations"), labels(alert.annotations));
  const links = el("div", "button-row");
  append(links, externalLink("Dashboard", alert.dashboard_url), externalLink("Panel", alert.panel_url), externalLink("Silence", alert.silence_url));
  if (links.childElementCount) body.append(links);
  details.append(body);
  return details;
}

function incidentSummaryRow(incident) {
  const row = el("div", "list-row");
  const main = el("div", "row-main");
  append(main, link(incident.title, `/incidents/${incident.id}`, "row-title"), el("span", "row-sub", `${incident.service} · ${dateTime(incident.updated_at)}`));
  append(row, main, append(el("div", "row-side"), badge(incident.severity), badge(incident.status)));
  return row;
}

function alertSummaryRow(alert) {
  const row = el("div", "list-row");
  const main = el("div", "row-main");
  const title = alert.incident_id ? link(alert.alert_name || alert.summary || alert.fingerprint, `/incidents/${alert.incident_id}`, "row-title") : el("span", "row-title", alert.alert_name || alert.summary || alert.fingerprint);
  append(main, title, el("span", "row-sub", `${alert.service} · ${dateTime(alert.received_at)}`));
  append(row, main, badge(alert.status));
  return row;
}

async function overview(ctx) {
  loading(ctx.root);
  const [incidents, alerts] = await Promise.all([
    request("/incidents", { signal: ctx.signal }),
    request("/alerts?limit=5&offset=0", { signal: ctx.signal }),
  ]);
  if (ctx.signal.aborted) return;
  const cards = el("div", "stats-grid");
  const metrics = [
    ["Total incidents", incidents.length, "All recorded incidents", ""],
    ["Open incidents", incidents.filter((item) => item.status === "open").length, "Currently active", "open"],
    ["Resolved incidents", incidents.filter((item) => item.status === "resolved").length, "Closed by alert state", "resolved"],
    ["Alert events", alerts.total, "Firing and resolved events", ""],
  ];
  for (const [name, value, note, type] of metrics) {
    append(cards, append(el("div", `stat-card ${type}`), el("div", "stat-label", name), el("div", "stat-value", value), el("div", "stat-foot", note)));
  }
  const recentIncidents = el("div", "panel-list");
  for (const incident of incidents.slice(0, 6)) recentIncidents.append(incidentSummaryRow(incident));
  if (!incidents.length) recentIncidents.append(empty("No incidents yet", "Incoming Grafana alerts will appear here after correlation."));
  const recentAlerts = el("div", "panel-list");
  for (const alert of alerts.items) recentAlerts.append(alertSummaryRow(alert));
  if (!alerts.items.length) recentAlerts.append(empty("No alerts yet", "Send a Grafana alert to start the flow."));
  ctx.root.replaceChildren(heading("OPERATIONS AT A GLANCE", "Overview", "Current activity across your incident workflow."), cards,
    append(el("div", "two-column"), panel("Recent incidents", recentIncidents, link("View all →", "/incidents", "text-link small")), panel("Latest alert events", recentAlerts, link("View all →", "/alerts", "text-link small"))));
}

function tableHeader(names) {
  const table = el("table", "data-table");
  const head = el("thead");
  const row = el("tr");
  for (const name of names) row.append(el("th", "", name));
  head.append(row);
  table.append(head);
  return table;
}

let fieldIndex = 0;

function labeledField(name, control, wide = false) {
  const label = el("label", "", name);
  control.id ||= `field-${++fieldIndex}`;
  label.htmlFor = control.id;
  return append(el("div", `field ${wide ? "field-wide" : ""}`), label, control);
}

async function incidents(ctx) {
  loading(ctx.root);
  const items = await request("/incidents", { signal: ctx.signal });
  if (ctx.signal.aborted) return;
  const search = el("input");
  search.type = "search";
  search.placeholder = "Search title or service";
  search.setAttribute("aria-label", "Search incidents by title or service");
  const state = el("select");
  for (const [value, name] of [["", "All states"], ["open", "Open"], ["resolved", "Resolved"]]) {
    const option = el("option", "", name); option.value = value; state.append(option);
  }
  const severity = el("select");
  for (const [value, name] of [["", "All severities"], ["critical", "Critical"], ["warning", "Warning"], ["info", "Info"], ["unknown", "Unknown"]]) {
    const option = el("option", "", name); option.value = value; severity.append(option);
  }
  const toolbar = el("div", "toolbar");
  const searchField = labeledField("SEARCH", search);
  searchField.classList.add("field-grow");
  append(toolbar, searchField, labeledField("STATUS", state), labeledField("SEVERITY", severity));
  const body = el("div");
  function update() {
    const query = search.value.trim().toLowerCase();
    const filtered = items.filter((item) => (!query || `${item.title} ${item.service}`.toLowerCase().includes(query)) && (!state.value || item.status === state.value) && (!severity.value || item.severity === severity.value));
    if (!filtered.length) { body.replaceChildren(empty("No matching incidents", "Adjust your filters or wait for new alert events.")); return; }
    const table = tableHeader(["INCIDENT", "SERVICE", "SEVERITY", "STATUS", "UPDATED"]);
    const tbody = el("tbody");
    for (const incident of filtered) {
      const row = el("tr");
      const title = append(el("td", "primary-cell"), link(incident.title, `/incidents/${incident.id}`, "text-link"), el("span", "secondary-cell mono", `Revision ${incident.revision}`));
      append(row, title, el("td", "", incident.service), append(el("td"), badge(incident.severity)), append(el("td"), badge(incident.status)), append(el("td"), timeNode(incident.updated_at)));
      tbody.append(row);
    }
    table.append(tbody);
    body.replaceChildren(table);
  }
  for (const control of [search, state, severity]) control.addEventListener("input", update);
  update();
  ctx.root.replaceChildren(heading("INCIDENT TRACKING", "Incidents", "Browse correlated alerts and follow their investigation history."), toolbar, panel(`${items.length} incidents`, body));
}

function timelineItem(alert) {
  const item = el("div", `timeline-item ${alert.status}`);
  const content = el("div");
  append(content, append(el("div", "timeline-title"), el("span", "", alert.alert_name || "Alert event"), badge(alert.status)), el("div", "timeline-meta", `${dateTime(alert.received_at)} · ${alert.severity} · ${alert.fingerprint}`));
  if (alert.summary) content.append(el("p", "timeline-copy", alert.summary));
  content.append(alertDetails(alert));
  append(item, el("div", "timeline-point"), content);
  return item;
}

async function incidentDetail(ctx, id) {
  loading(ctx.root);
  const [incident, history] = await Promise.all([
    request(`/incidents/${id}`, { signal: ctx.signal }),
    request(`/incidents/${id}/investigations`, { signal: ctx.signal }),
  ]);
  if (ctx.signal.aborted) return;
  let idempotencyKey = null;
  const investigate = button("Start investigation →", "button button-primary");
  investigate.addEventListener("click", async () => {
    idempotencyKey ||= crypto.randomUUID?.() || `${Date.now()}-${Math.random().toString(36).slice(2)}`;
    investigate.disabled = true;
    try {
      const result = await request(`/incidents/${id}/investigations`, { method: "POST", headers: { "Idempotency-Key": idempotencyKey }, signal: ctx.signal });
      idempotencyKey = null;
      ctx.navigate(`/investigations/${result.id}`);
    } catch (error) {
      if (error.status === 409 && error.metadata.investigation_id) {
        idempotencyKey = null;
        ctx.navigate(`/investigations/${error.metadata.investigation_id}`);
      } else if (error.status !== 401 && error.name !== "AbortError") {
        ctx.toast(error.message, true);
      }
    } finally { investigate.disabled = false; }
  });
  const headingNode = heading("INCIDENT DETAILS", incident.title, `${incident.service} · Revision ${incident.revision}`, investigate);
  const summary = el("div", "meta-strip");
  append(summary, badge(incident.status), badge(incident.severity), append(el("span"), "Started ", timeNode(incident.started_at)), append(el("span"), "Last activity ", timeNode(incident.updated_at)));
  headingNode.firstChild.append(summary);
  const timeline = el("div", "timeline");
  for (const alert of incident.alerts) timeline.append(timelineItem(alert));
  if (!incident.alerts.length) timeline.append(empty("No linked alerts", "This incident has no alert events yet."));
  const investigations = el("div", "investigation-list");
  for (const item of history) {
    const card = el("div", "investigation-item");
    append(card, append(el("div", "investigation-item-top"), link(`Investigation ${item.id.slice(0, 8)}`, `/investigations/${item.id}`), badge(item.status)), el("span", "row-sub", `${dateTime(item.requested_at)} · Revision ${item.incident_revision} · ${item.analyzer_version}`));
    investigations.append(card);
  }
  if (!history.length) investigations.append(empty("No investigations", "Start one to analyze the available evidence."));
  const facts = append(el("div", "panel-body"), keyValues([
    ["Incident ID", incident.id],
    ["Service", incident.service],
    ["Started", dateTime(incident.started_at)],
    ["Resolved", dateTime(incident.resolved_at)],
    ["Alert events", incident.alerts.length],
  ]));
  ctx.root.replaceChildren(headingNode, append(el("div", "detail-grid"), panel("Alert timeline", timeline), append(el("div"), panel("Incident facts", facts), panel("Investigations", investigations))));
}

function resultSection(title, content) {
  return append(el("section", "result-section"), el("h3", "", title), content);
}

function itemList(items, renderItem = (value) => el("span", "", value)) {
  const list = el("ul");
  for (const value of items || []) list.append(append(el("li"), renderItem(value)));
  return list;
}

function investigationResult(result) {
  if (!result) return empty("Waiting for analysis", "The worker has not saved a result yet.");
  if (result.schema === "legacy_report.v1") {
    return append(el("div", "panel-body"), el("pre", "result-summary", JSON.stringify(result.report, null, 2)));
  }
  const body = el("div", "panel-body");
  if (result.outcome === "insufficient_evidence") body.append(el("div", "result-note", "The available evidence was insufficient for an analysis."));
  body.append(resultSection("Summary", el("p", "result-summary", result.summary || "No summary provided.")));
  if (result.hypotheses?.length) body.append(resultSection("Hypotheses", itemList(result.hypotheses, (item) => {
    const wrapper = el("div");
    append(wrapper, el("strong", "", item.statement || "Hypothesis"), el("div", "row-sub mono", (item.evidence_ids || []).join(" · ")));
    return wrapper;
  })));
  if (result.evidence?.length) body.append(resultSection("Cited evidence", itemList(result.evidence, (item) => el("span", "", `${item.id || "Evidence"} · ${item.summary || item.title || item.source || item.content || item.kind || ""}`))));
  if (result.recommended_checks?.length) body.append(resultSection("Recommended checks", itemList(result.recommended_checks)));
  if (result.missing_information?.length) body.append(resultSection("Missing information", itemList(result.missing_information)));
  if (result.retrieved_knowledge?.length) {
    const knowledge = el("div");
    for (const item of result.retrieved_knowledge) append(knowledge, append(el("div", "evidence-card"), el("strong", "", `${item.title || item.source || "Knowledge"} · ${item.evidence_id || ""}`), el("p", "", item.content || "")));
    body.append(resultSection("Retrieved knowledge", knowledge));
  }
  return body;
}

function attemptList(items) {
  if (!items?.length) return empty("No attempts yet", "The worker has not started processing this investigation.");
  const wrapper = el("div", "panel-list");
  for (const attempt of items) {
    const row = el("div", "investigation-item");
    append(row, append(el("div", "investigation-item-top"), el("strong", "small", `Attempt ${attempt.attempt_number}`), badge(attempt.status)), el("span", "row-sub", `${dateTime(attempt.started_at)} · ${attempt.provider || "—"} / ${attempt.model || "—"}`));
    if (attempt.error_message) row.append(el("p", "form-error", attempt.error_message));
    if (attempt.total_tokens !== null && attempt.total_tokens !== undefined) row.append(el("div", "row-sub", `${attempt.total_tokens} tokens · estimated $${attempt.estimated_cost_usd ?? "—"} · ${attempt.latency_ms ?? "—"} ms`));
    wrapper.append(row);
  }
  return wrapper;
}

async function investigationDetail(ctx, id) {
  loading(ctx.root);
  let timer = null;
  let previous = null;
  let terminal = false;
  let generation = 0;
  async function load() {
    clearTimeout(timer);
    const currentGeneration = ++generation;
    const item = await request(`/investigations/${id}`, { signal: ctx.signal });
    if (ctx.signal.aborted || currentGeneration !== generation) return;
    terminal = ["completed", "failed"].includes(item.status);
    const next = JSON.stringify(item);
    if (next !== previous) {
      const head = heading("INVESTIGATION", `Investigation ${item.id.slice(0, 8)}`, `Incident revision ${item.incident_revision} · ${item.analyzer_version}`, link("← Back to incident", `/incidents/${item.incident_id}`, "button"));
      append(head.firstChild, append(el("div", "meta-strip"), badge(item.status), append(el("span"), "Requested ", timeNode(item.requested_at)), append(el("span"), "Completed ", timeNode(item.completed_at))));
      const facts = append(el("div", "panel-body"), keyValues([
        ["Investigation ID", item.id],
        ["Incident revision", item.incident_revision],
        ["Analyzer", item.analyzer_version],
        ["Attempts", item.attempt_count],
        ["Next attempt", dateTime(item.next_attempt_at)],
        ["Error", item.error_message],
      ]));
      const main = el("div");
      if (item.status === "queued" || item.status === "running" || item.status === "retry_wait") main.append(el("div", "result-note", "This investigation is in progress. The view updates automatically while this tab is active."));
      append(main, panel("Analysis result", investigationResult(item.result)));
      ctx.root.replaceChildren(head, append(el("div", "detail-grid"), main, append(el("div"), panel("Details", facts), panel("Attempts", attemptList(item.attempts)))));
      previous = next;
    }
    if (!terminal && !document.hidden && !ctx.signal.aborted) timer = setTimeout(() => load().catch((error) => {
      if (!ctx.signal.aborted && error.status !== 401 && error.name !== "AbortError") showError(ctx.root, error, ctx.refresh);
    }), 3000);
  }
  function visibilityChanged() {
    clearTimeout(timer);
    if (document.hidden) { generation++; return; }
    if (!terminal && !document.hidden && !ctx.signal.aborted) load().catch((error) => {
      if (!ctx.signal.aborted && error.status !== 401 && error.name !== "AbortError") showError(ctx.root, error, ctx.refresh);
    });
  }
  document.addEventListener("visibilitychange", visibilityChanged);
  ctx.signal.addEventListener("abort", () => {
    clearTimeout(timer);
    document.removeEventListener("visibilitychange", visibilityChanged);
  }, { once: true });
  await load();
}

function pagination(page, onPage) {
  const footer = el("div", "table-footer");
  const first = page.total ? page.offset + 1 : 0;
  const last = Math.min(page.total, page.offset + page.items.length);
  const previous = button("← Previous", "button button-quiet");
  const next = button("Next →", "button button-quiet");
  previous.disabled = page.offset === 0;
  next.disabled = page.offset + page.limit >= page.total;
  previous.addEventListener("click", () => onPage(Math.max(0, page.offset - page.limit)));
  next.addEventListener("click", () => onPage(page.offset + page.limit));
  append(footer, el("span", "", `${first}–${last} of ${page.total}`), append(el("div", "pagination"), previous, next));
  return footer;
}

async function alerts(ctx) {
  const service = el("input");
  service.placeholder = "Exact service name";
  service.maxLength = 160;
  const status = el("select");
  for (const [value, name] of [["", "All events"], ["firing", "Firing"], ["resolved", "Resolved"]]) {
    const option = el("option", "", name); option.value = value; status.append(option);
  }
  const apply = button("Apply filters");
  const serviceField = labeledField("SERVICE", service);
  serviceField.classList.add("field-grow");
  const toolbar = append(el("div", "toolbar"), serviceField, labeledField("EVENT STATUS", status), apply);
  const list = el("div", "alert-list");
  const footer = el("div");
  let serial = 0;
  async function load(offset = 0) {
    const sequence = ++serial;
    loading(list);
    footer.replaceChildren();
    const query = new URLSearchParams({ limit: "50", offset: String(offset) });
    if (service.value.trim()) query.set("service", service.value.trim());
    if (status.value) query.set("status", status.value);
    const page = await request(`/alerts?${query}`, { signal: ctx.signal });
    if (ctx.signal.aborted || sequence !== serial) return;
    list.replaceChildren();
    if (!page.items.length) list.append(empty("No alert events", "Try another filter or send a Grafana alert."));
    for (const alert of page.items) {
      const card = el("article", `alert-card ${alert.status}`);
      const main = el("div", "row-main");
      append(main, el("strong", "row-title", alert.alert_name || alert.summary || "Alert event"), el("span", "row-sub", `${alert.service} · ${dateTime(alert.received_at)} · ${alert.fingerprint}`));
      const side = append(el("div", "row-side"), badge(alert.severity), badge(alert.status));
      append(card, append(el("div", "alert-card-head"), main, side));
      if (alert.summary) card.append(el("p", "alert-description", alert.summary));
      const related = el("div", "row-sub");
      related.append(alert.incident_id ? link("View related incident →", `/incidents/${alert.incident_id}`) : el("span", "", "Pending correlation or no linked incident"));
      card.append(related, append(el("div", "alert-details"), alertDetails(alert)));
      list.append(card);
    }
    footer.append(pagination(page, (nextOffset) => load(nextOffset).catch((error) => {
      if (!ctx.signal.aborted && error.status !== 401 && error.name !== "AbortError") showError(list, error, () => load(nextOffset));
    })));
  }
  apply.addEventListener("click", () => load().catch((error) => {
    if (!ctx.signal.aborted && error.status !== 401 && error.name !== "AbortError") showError(list, error, () => load());
  }));
  service.addEventListener("keydown", (event) => { if (event.key === "Enter") apply.click(); });
  append(ctx.root, heading("EVENT STREAM", "Alerts", "Every firing and resolved event received from Grafana."), toolbar, list, footer);
  await load();
}

async function knowledge(ctx) {
  const service = el("input"); service.required = true; service.maxLength = 160; service.placeholder = "e.g. payments-api";
  const source = el("input"); source.required = true; source.maxLength = 500; source.placeholder = "e.g. runbooks/payments.md";
  const title = el("input"); title.required = true; title.maxLength = 300; title.placeholder = "Document title";
  const version = el("input"); version.required = true; version.maxLength = 100; version.placeholder = "e.g. 1.0";
  const content = el("textarea"); content.placeholder = "Paste Markdown or plain text here";
  const file = el("input"); file.type = "file"; file.accept = ".md,.txt,text/plain,text/markdown";
  const form = el("form", "panel-body");
  const grid = el("div", "form-grid");
  append(grid, labeledField("SERVICE", service), labeledField("SOURCE", source), labeledField("TITLE", title), labeledField("VERSION", version), labeledField("MARKDOWN OR TEXT", content, true), labeledField("OR SELECT A LOCAL .MD / .TXT FILE", file, true));
  const submit = el("button", "button button-primary", "Save document"); submit.type = "submit";
  const note = el("span", "muted", "The same service and source replace the existing document.");
  const feedback = el("p", "form-error"); feedback.setAttribute("role", "alert");
  append(form, grid, append(el("div", "form-actions"), submit, note), feedback);
  const list = el("div");
  const footer = el("div");
  async function load(offset = 0) {
    loading(list);
    footer.replaceChildren();
    const page = await request(`/knowledge/documents?limit=50&offset=${offset}`, { signal: ctx.signal });
    if (ctx.signal.aborted) return;
    if (!page.items.length && offset > 0 && page.total > 0) return load(Math.max(0, offset - page.limit));
    if (!page.items.length) { list.replaceChildren(empty("No knowledge documents", "Add a runbook to make it available for future investigations.")); return; }
    const table = tableHeader(["DOCUMENT", "SERVICE", "VERSION", "CHUNKS", "UPDATED", ""]);
    const body = el("tbody");
    for (const item of page.items) {
      const row = el("tr");
      const name = append(el("td", "primary-cell"), el("span", "", item.title), el("span", "secondary-cell", item.source));
      const remove = button("Delete", "button button-danger");
      remove.addEventListener("click", async () => {
        if (!window.confirm(`Delete “${item.title}” from the knowledge index?`)) return;
        remove.disabled = true;
        try {
          await request(`/knowledge/documents/${item.id}`, { method: "DELETE", signal: ctx.signal });
          ctx.toast("Document deleted.");
          await load(offset);
        } catch (error) {
          if (error.status !== 401 && error.name !== "AbortError") ctx.toast(error.message, true);
          remove.disabled = false;
        }
      });
      append(row, name, el("td", "", item.service), el("td", "", item.version), el("td", "", item.chunk_count), append(el("td"), timeNode(item.updated_at)), append(el("td"), remove));
      body.append(row);
    }
    table.append(body);
    list.replaceChildren(table);
    footer.append(pagination(page, (nextOffset) => load(nextOffset).catch((error) => {
      if (!ctx.signal.aborted && error.status !== 401 && error.name !== "AbortError") showError(list, error, () => load(nextOffset));
    })));
  }
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    feedback.textContent = "";
    submit.disabled = true;
    submit.textContent = "Saving document…";
    try {
      const text = file.files[0] ? await file.files[0].text() : content.value;
      if (!text.trim()) { feedback.textContent = "Enter text or select a file."; return; }
      if (text.length > 2_000_000) { feedback.textContent = "Document exceeds the API limit of 2,000,000 characters."; return; }
      const result = await request("/knowledge/documents", {
        method: "POST",
        body: { service: service.value.trim(), source: source.value.trim(), title: title.value.trim(), version: version.value.trim(), content: text },
        signal: ctx.signal,
      });
      ctx.toast(`Document saved with ${result.chunks} chunks.`);
      form.reset();
      await load();
    } catch (error) {
      if (error.code === "knowledge_not_enabled") feedback.textContent = "Knowledge ingestion is disabled on this server. Enable RAG to add documents.";
      else if (error.status !== 401 && error.name !== "AbortError") feedback.textContent = error.message;
    } finally {
      submit.disabled = false;
      submit.textContent = "Save document";
    }
  });
  append(ctx.root, heading("OPERATIONAL CONTEXT", "Knowledge", "Runbooks available to the investigation worker in this environment."), panel("Add or replace document", form), panel("Indexed documents", list), footer);
  await load();
}

export async function renderRoute(route, ctx) {
  if (route.name === "overview") return overview(ctx);
  if (route.name === "incidents") return incidents(ctx);
  if (route.name === "incident") return incidentDetail(ctx, route.id);
  if (route.name === "investigation") return investigationDetail(ctx, route.id);
  if (route.name === "alerts") return alerts(ctx);
  if (route.name === "knowledge") return knowledge(ctx);
  ctx.root.replaceChildren(heading("NAVIGATION", "Page not found", "The requested view does not exist."), link("Go to overview →", "/"));
}
